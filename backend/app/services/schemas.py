"""Versioned vertical schemas. A new field is a new version, not a migration."""

from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session, select

from app.domain.catalog import normalize_schema_key
from app.domain.validation import check_schema_document, tighten_schema
from app.models import VerticalSchema


def canonical(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True)


def latest_schemas(session: Session) -> list[VerticalSchema]:
    rows = session.exec(select(VerticalSchema).order_by(VerticalSchema.key, VerticalSchema.version.desc())).all()
    latest: dict[str, VerticalSchema] = {}
    for row in rows:
        latest.setdefault(row.key, row)
    return list(latest.values())


def find_schema(session: Session, key: str) -> VerticalSchema | None:
    key = normalize_schema_key(key)
    rows = session.exec(
        select(VerticalSchema).where(VerticalSchema.key == key).order_by(VerticalSchema.version.desc())
    ).all()
    return rows[0] if rows else None


def save_schema_version(
    session: Session,
    *,
    key: str,
    title: str,
    description: str,
    document: dict[str, Any],
) -> VerticalSchema:
    key = normalize_schema_key(key)
    document = tighten_schema(dict(document))
    check_schema_document(document)
    current = find_schema(session, key)
    if current is not None and canonical(current.json_schema) == canonical(document):
        if title:
            current.title = title
        if description:
            current.description = description
        return current
    version = (current.version + 1) if current else 1
    row = VerticalSchema(
        key=key,
        version=version,
        title=title or key,
        description=description or "",
        json_schema=document,
        parent_id=current.id if current else None,
        status="proposed",
    )
    session.add(row)
    session.flush()
    return row
