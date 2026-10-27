"""Map the central catalog onto rows, sealing adapter config on the way in."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.crypto import decrypt_json, encrypt_json
from app.domain.catalog import (
    AdapterBinding,
    BusinessCatalog,
    ConversionPointDraft,
    Offering,
    PriceRange,
    Seller,
    TrustInfo,
    Work,
    assign_slugs,
)
from app.domain.conversion_templates import default_input_schema
from app.domain.validation import SchemaValidationError, check_schema_document, tighten_schema, validate_catalog_extensions
from app.models import Business as BusinessRow
from app.models import Conversion, ConversionPoint, Offering as OfferingRow
from app.models import VerticalSchema, Work as WorkRow
from app.models import utcnow


def prepare_catalog(catalog: BusinessCatalog) -> BusinessCatalog:
    assign_slugs(catalog)
    for point in catalog.conversion_points:
        schema = point.input_schema or {}
        if point.type != "external_link" and not schema.get("properties"):
            point.input_schema = default_input_schema(point.type)
        elif not schema:
            point.input_schema = default_input_schema(point.type)
        point.input_schema = tighten_schema(dict(point.input_schema))
        check_schema_document(point.input_schema)
        if not point.adapters:
            point.adapters = [AdapterBinding(key="internal", config={})]
    return catalog


def seal_catalog(catalog: BusinessCatalog) -> dict[str, Any]:
    data = catalog.model_dump(mode="json")
    for point in data.get("conversion_points") or []:
        sealed = []
        for adapter in point.get("adapters") or []:
            sealed.append(
                {
                    "key": adapter.get("key") or "internal",
                    "config_encrypted": encrypt_json(adapter.get("config") or {}),
                }
            )
        point["adapters"] = sealed
    return data


def open_catalog(data: dict[str, Any]) -> BusinessCatalog:
    payload = dict(data)
    points = []
    for point in payload.get("conversion_points") or []:
        item = dict(point)
        opened = []
        for adapter in item.get("adapters") or []:
            if adapter.get("config_encrypted"):
                try:
                    config = decrypt_json(adapter["config_encrypted"])
                except Exception:  # noqa: BLE001
                    config = {}
            else:
                config = adapter.get("config") or {}
            opened.append({"key": adapter.get("key") or "internal", "config": config})
        item["adapters"] = opened
        points.append(item)
    payload["conversion_points"] = points
    return BusinessCatalog.model_validate(payload)


def _offerings(session: Session, business_id: Any) -> list[OfferingRow]:
    return list(
        session.exec(select(OfferingRow).where(OfferingRow.business_id == business_id).order_by(OfferingRow.position)).all()
    )


def _works(session: Session, business_id: Any) -> list[WorkRow]:
    return list(session.exec(select(WorkRow).where(WorkRow.business_id == business_id).order_by(WorkRow.position)).all())


def _points(session: Session, business_id: Any) -> list[ConversionPoint]:
    return list(
        session.exec(
            select(ConversionPoint).where(ConversionPoint.business_id == business_id).order_by(ConversionPoint.position)
        ).all()
    )


def load_catalog(session: Session, business: BusinessRow, *, include_adapter_config: bool) -> BusinessCatalog:
    offerings = _offerings(session, business.id)
    works = _works(session, business.id)
    points = _points(session, business.id)
    slug_by_offering = {row.id: row.slug for row in offerings}
    schema = session.get(VerticalSchema, business.vertical_schema_id) if business.vertical_schema_id else None
    point_models: list[ConversionPointDraft] = []
    for point in points:
        if not include_adapter_config and not point.enabled:
            continue
        adapters: list[AdapterBinding] = []
        if include_adapter_config:
            for stored in point.adapters or []:
                if stored.get("config_encrypted"):
                    try:
                        config = decrypt_json(stored["config_encrypted"])
                    except Exception:  # noqa: BLE001
                        config = {}
                else:
                    config = stored.get("config") or {}
                adapters.append(AdapterBinding(key=stored.get("key") or "internal", config=config))
        point_models.append(
            ConversionPointDraft(
                key=point.key,
                type=point.type,  # type: ignore[arg-type]
                name=point.name,
                description=point.description,
                input_schema=point.input_schema or {},
                external_url=point.external_url,
                offering_slug=slug_by_offering.get(point.offering_id) if point.offering_id else None,
                adapters=adapters,
                enabled=point.enabled,
            )
        )
    return BusinessCatalog(
        name=business.name,
        slug=business.slug,
        summary=business.summary,
        description=business.description,
        seller=Seller.model_validate(business.seller or {"name": business.name}),
        service_area=list(business.service_area or []),
        tags=list(business.tags or []),
        price_range=PriceRange.model_validate(business.price_range) if business.price_range else None,
        trust=TrustInfo.model_validate(business.trust or {}),
        schema_org_type=business.schema_org_type,
        images=list(business.images or []),
        offerings=[Offering.model_validate(row.model_dump()) for row in offerings],
        works=[
            Work.model_validate(
                {
                    "title": row.title,
                    "slug": row.slug,
                    "description": row.description,
                    "year": row.year,
                    "client": row.client,
                    "location": row.location,
                    "url": row.url,
                    "images": row.images,
                    "schema_org_type": row.schema_org_type,
                    "extension": row.extension,
                }
            )
            for row in works
        ],
        conversion_points=point_models,
        extension=dict(business.extension or {}),
        source_urls=list(business.source_urls or []),
        source_description=business.source_description or "",
        vertical_key=schema.key if schema else business.vertical_key,
    )


def apply_catalog(
    session: Session,
    business: BusinessRow,
    catalog: BusinessCatalog,
    schema_row: VerticalSchema | None,
) -> None:
    """Replace the live rows for a business. Caller commits."""
    catalog = prepare_catalog(catalog)
    document = schema_row.json_schema if schema_row else None
    validate_catalog_extensions(document, catalog)
    conflict = session.exec(
        select(BusinessRow).where(BusinessRow.slug == catalog.slug, BusinessRow.id != business.id)
    ).first()
    if conflict is not None:
        raise SchemaValidationError([f"スラッグ {catalog.slug} は既に使われています"])

    business.name = catalog.name
    business.slug = catalog.slug
    business.summary = catalog.summary
    business.description = catalog.description
    business.seller = catalog.seller.model_dump(mode="json")
    business.service_area = list(catalog.service_area)
    business.tags = list(catalog.tags)
    business.price_range = catalog.price_range.model_dump(mode="json") if catalog.price_range else None
    business.trust = catalog.trust.model_dump(mode="json")
    business.extension = dict(catalog.extension or {})
    business.images = [item.model_dump(mode="json") for item in catalog.images]
    business.source_urls = list(catalog.source_urls)
    business.source_description = catalog.source_description
    business.schema_org_type = catalog.schema_org_type or "ProfessionalService"
    business.vertical_schema_id = schema_row.id if schema_row else None
    business.vertical_key = schema_row.key if schema_row else catalog.vertical_key
    business.updated_at = utcnow()

    for row in _points(session, business.id):
        row.offering_id = None
    session.flush()
    for row in _offerings(session, business.id):
        session.delete(row)
    for row in _works(session, business.id):
        session.delete(row)
    session.flush()

    offering_ids: dict[str, Any] = {}
    for index, offering in enumerate(catalog.offerings):
        row = OfferingRow(
            business_id=business.id,
            slug=offering.slug,
            name=offering.name,
            kind=offering.kind,
            description=offering.description,
            price_range=offering.price_range.model_dump(mode="json") if offering.price_range else None,
            tags=list(offering.tags),
            area=list(offering.area),
            images=[item.model_dump(mode="json") for item in offering.images],
            extension=dict(offering.extension or {}),
            schema_org_type=offering.schema_org_type,
            position=index,
        )
        session.add(row)
        session.flush()
        offering_ids[offering.slug] = row.id

    for index, work in enumerate(catalog.works):
        session.add(
            WorkRow(
                business_id=business.id,
                slug=work.slug,
                title=work.title,
                description=work.description,
                year=work.year,
                client=work.client,
                location=work.location,
                url=work.url,
                images=[item.model_dump(mode="json") for item in work.images],
                extension=dict(work.extension or {}),
                schema_org_type=work.schema_org_type,
                position=index,
            )
        )

    existing = {row.key: row for row in _points(session, business.id)}
    seen: set[str] = set()
    for index, point in enumerate(catalog.conversion_points):
        seen.add(point.key)
        stored_adapters = [
            {"key": binding.key, "config_encrypted": encrypt_json(binding.config)} for binding in point.adapters
        ]
        row = existing.get(point.key)
        if row is None:
            row = ConversionPoint(business_id=business.id, key=point.key, type=point.type, name=point.name)
            session.add(row)
        row.type = point.type
        row.name = point.name
        row.description = point.description
        row.input_schema = point.input_schema
        row.external_url = point.external_url
        row.adapters = stored_adapters
        row.enabled = point.enabled
        row.position = index
        row.offering_id = offering_ids.get(point.offering_slug) if point.offering_slug else None
    for key, row in existing.items():
        if key in seen:
            continue
        used = session.exec(select(Conversion).where(Conversion.conversion_point_id == row.id)).first()
        if used is None:
            session.delete(row)
        else:
            row.enabled = False
    if schema_row is not None:
        schema_row.status = "active"
