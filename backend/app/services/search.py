"""Attribute filters for published businesses. Matching is lexical, never embedded."""

from __future__ import annotations

import uuid

from sqlalchemy import Integer, String, and_, cast, func, or_
from sqlmodel import Session, select

from app.models import Business, ConversionPoint, Offering


def search_businesses(
    session: Session,
    *,
    q: str | None = None,
    tags: list[str] | None = None,
    area: str | None = None,
    vertical: str | None = None,
    kind: str | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    limit: int = 20,
) -> list[Business]:
    stmt = select(Business).where(Business.status == "published")
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Business.name.ilike(like),
                Business.summary.ilike(like),
                Business.description.ilike(like),
                cast(Business.tags, String).ilike(like),
            )
        )
    if vertical:
        stmt = stmt.where(Business.vertical_key == vertical.strip())
    if area:
        stmt = stmt.where(cast(Business.service_area, String).ilike(f"%{area.strip()}%"))
    for tag in tags or []:
        cleaned = tag.strip()
        if cleaned:
            stmt = stmt.where(cast(Business.tags, String).ilike(f"%{cleaned}%"))
    if kind:
        stmt = stmt.where(Business.id.in_(select(Offering.business_id).where(Offering.kind == kind)))
    if price_min is not None or price_max is not None:
        min_amount = cast(Business.price_range["min_amount"].astext, Integer)
        max_amount = cast(Business.price_range["max_amount"].astext, Integer)
        effective_min = func.coalesce(min_amount, max_amount)
        effective_max = func.coalesce(max_amount, min_amount)
        overlap = []
        if price_min is not None:
            overlap.append(effective_max >= price_min)
        if price_max is not None:
            overlap.append(effective_min <= price_max)
        stmt = stmt.where(or_(Business.price_range.is_(None), and_(*overlap)))
    stmt = stmt.order_by(Business.name).limit(max(1, min(limit, 50)))
    return list(session.exec(stmt).all())


def published_business(session: Session, business_id: uuid.UUID | None = None, slug: str | None = None) -> Business | None:
    if business_id is not None:
        row = session.get(Business, business_id)
        if row is None or row.status != "published":
            return None
        return row
    if slug:
        return session.exec(select(Business).where(Business.slug == slug, Business.status == "published")).first()
    return None


def find_offering(session: Session, offering_id: uuid.UUID | None = None, business_slug: str | None = None, offering_slug: str | None = None):
    if offering_id is not None:
        row = session.get(Offering, offering_id)
        if row is None:
            return None, None
        business = published_business(session, business_id=row.business_id)
        if business is None:
            return None, None
        return business, row
    business = published_business(session, slug=business_slug)
    if business is None or not offering_slug:
        return None, None
    row = session.exec(
        select(Offering).where(Offering.business_id == business.id, Offering.slug == offering_slug)
    ).first()
    return business, row


def list_points(session: Session, business_id: uuid.UUID | None = None, business_slug: str | None = None):
    business = None
    if business_id or business_slug:
        business = published_business(session, business_id=business_id, slug=business_slug)
        if business is None:
            return []
        stmt = select(ConversionPoint).where(
            ConversionPoint.business_id == business.id, ConversionPoint.enabled == True  # noqa: E712
        )
    else:
        published_ids = select(Business.id).where(Business.status == "published")
        stmt = select(ConversionPoint).where(
            ConversionPoint.enabled == True,  # noqa: E712
            ConversionPoint.business_id.in_(published_ids),
        )
    return list(session.exec(stmt.order_by(ConversionPoint.position)).all())
