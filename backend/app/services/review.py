"""Operator review: edit the proposed catalog, then publish it onto the live rows."""

from __future__ import annotations

import uuid

from sqlmodel import Session, select

from app.domain.catalog import BusinessCatalog
from app.domain.completeness import compute_completeness
from app.domain.validation import SchemaValidationError
from app.models import Business, GenerationRun, VerticalSchema, utcnow
from app.services.persistence import apply_catalog, open_catalog, prepare_catalog, seal_catalog
from app.services.schemas import find_schema, save_schema_version


def latest_run(session: Session, business_id: uuid.UUID) -> GenerationRun | None:
    rows = session.exec(
        select(GenerationRun).where(GenerationRun.business_id == business_id).order_by(GenerationRun.created_at.desc())
    ).all()
    return rows[0] if rows else None


def save_review(
    session: Session,
    business: Business,
    catalog: BusinessCatalog,
    *,
    schema_key: str | None,
    schema_title: str,
    schema_description: str,
    schema_document: dict | None,
) -> GenerationRun:
    run = latest_run(session, business.id)
    if run is None:
        run = GenerationRun(business_id=business.id, status="review", step="edit", model="")
        session.add(run)
        session.flush()
    schema_row = None
    if schema_document is not None:
        schema_row = save_schema_version(
            session,
            key=schema_key or catalog.vertical_key or "vertical",
            title=schema_title or schema_key or "vertical",
            description=schema_description,
            document=schema_document,
        )
        run.vertical_schema_id = schema_row.id
        catalog.vertical_key = schema_row.key
    elif run.vertical_schema_id:
        schema_row = session.get(VerticalSchema, run.vertical_schema_id)
    if schema_row is not None:
        catalog.vertical_key = schema_row.key
    catalog = prepare_catalog(catalog)
    document = schema_row.json_schema if schema_row is not None else None
    from app.domain.validation import validate_catalog_extensions

    validate_catalog_extensions(document, catalog)
    business.completeness = compute_completeness(catalog)
    run.extracted = seal_catalog(catalog)
    run.status = "review"
    run.step = "edit"
    run.error = None
    if business.status != "published":
        business.status = "review"
        business.name = catalog.name
        business.summary = catalog.summary
        business.vertical_key = catalog.vertical_key
        if schema_row is not None:
            business.vertical_schema_id = schema_row.id
    business.updated_at = utcnow()
    business.last_error = None
    session.commit()
    session.refresh(run)
    return run


def publish_business(session: Session, business: Business) -> Business:
    run = latest_run(session, business.id)
    if run is None or not run.extracted:
        raise SchemaValidationError(["公開できるカタログがありません。先に生成するか、レビューを保存してください。"])
    catalog = prepare_catalog(open_catalog(run.extracted))
    from app.models import VerticalSchema

    schema_row = session.get(VerticalSchema, run.vertical_schema_id) if run.vertical_schema_id else None
    if schema_row is None and catalog.vertical_key:
        schema_row = find_schema(session, catalog.vertical_key)
    apply_catalog(session, business, catalog, schema_row)
    business.status = "published"
    business.published_at = business.published_at or utcnow()
    business.last_error = None
    run.status = "published"
    run.error = None
    run.finished_at = utcnow()
    session.commit()
    session.refresh(business)
    return business
