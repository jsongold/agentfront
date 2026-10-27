"""Persistence tables. Vertical-specific fields live in JSONB, not new columns."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid_pk() -> Any:
    return Field(default_factory=uuid.uuid4, primary_key=True)


def _json(default: Any) -> Any:
    factory = dict if default == "object" else list
    return Field(default_factory=factory, sa_column=Column(JSONB, nullable=False))


class Business(SQLModel, table=True):
    __tablename__ = "businesses"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    slug: str = Field(index=True, unique=True, max_length=160)
    name: str = Field(max_length=300)
    summary: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    description: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    status: str = Field(default="draft", index=True, max_length=32)
    seller: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    service_area: list[Any] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    tags: list[Any] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    price_range: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))
    trust: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    extension: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    completeness: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))
    images: list[Any] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    source_urls: list[Any] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    source_description: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    schema_org_type: str = Field(default="ProfessionalService", max_length=80)
    vertical_key: str | None = Field(default=None, index=True, max_length=80)
    vertical_schema_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("vertical_schemas.id", ondelete="SET NULL")),
    )
    last_error: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    published_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class VerticalSchema(SQLModel, table=True):
    __tablename__ = "vertical_schemas"
    __table_args__ = (UniqueConstraint("key", "version", name="uq_vertical_schema_version"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    key: str = Field(index=True, max_length=80)
    version: int = Field(default=1)
    title: str = Field(max_length=200)
    description: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    json_schema: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    parent_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("vertical_schemas.id", ondelete="SET NULL")),
    )
    status: str = Field(default="proposed", max_length=32)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Offering(SQLModel, table=True):
    __tablename__ = "offerings"
    __table_args__ = (UniqueConstraint("business_id", "slug", name="uq_offering_slug"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    business_id: uuid.UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    slug: str = Field(max_length=160)
    name: str = Field(max_length=300)
    kind: str = Field(default="service", max_length=32)
    description: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    price_range: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))
    tags: list[Any] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    area: list[Any] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    images: list[Any] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    extension: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    schema_org_type: str = Field(default="Service", max_length=80)
    position: int = Field(default=0)


class Work(SQLModel, table=True):
    __tablename__ = "works"
    __table_args__ = (UniqueConstraint("business_id", "slug", name="uq_work_slug"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    business_id: uuid.UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    slug: str = Field(max_length=160)
    title: str = Field(max_length=300)
    description: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    year: int | None = None
    client: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=300)
    url: str | None = Field(default=None, sa_column=Column(Text))
    images: list[Any] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    extension: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    schema_org_type: str = Field(default="CreativeWork", max_length=80)
    position: int = Field(default=0)


class ConversionPoint(SQLModel, table=True):
    __tablename__ = "conversion_points"
    __table_args__ = (UniqueConstraint("business_id", "key", name="uq_conversion_point_key"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    business_id: uuid.UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    offering_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("offerings.id", ondelete="SET NULL")),
    )
    key: str = Field(max_length=80)
    type: str = Field(max_length=40)
    name: str = Field(max_length=300)
    description: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    input_schema: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    external_url: str | None = Field(default=None, sa_column=Column(Text))
    adapters: list[Any] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    enabled: bool = Field(default=True)
    position: int = Field(default=0)


class Conversion(SQLModel, table=True):
    __tablename__ = "conversions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversion_point_id: uuid.UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("conversion_points.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    business_id: uuid.UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    agent_name: str = Field(default="", max_length=200)
    request_text: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    user_agent: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    agent_class: str = Field(default="unknown", max_length=80)
    status: str = Field(default="recorded", max_length=32)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )


class Delivery(SQLModel, table=True):
    __tablename__ = "deliveries"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversion_id: uuid.UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("conversions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    adapter_key: str = Field(max_length=80)
    status: str = Field(max_length=32)
    detail: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class CrawlDocument(SQLModel, table=True):
    __tablename__ = "crawl_documents"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    business_id: uuid.UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    generation_run_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("generation_runs.id", ondelete="CASCADE")),
    )
    url: str = Field(sa_column=Column(Text, nullable=False))
    ok: bool = Field(default=False)
    title: str = Field(default="", max_length=500)
    text: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    metadata_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    error: str | None = Field(default=None, sa_column=Column(Text))
    fetched_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class GenerationRun(SQLModel, table=True):
    __tablename__ = "generation_runs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    business_id: uuid.UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    status: str = Field(default="queued", max_length=32)
    step: str = Field(default="queued", max_length=40)
    error: str | None = Field(default=None, sa_column=Column(Text))
    model: str = Field(default="", max_length=120)
    schema_proposal: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))
    extracted: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))
    vertical_schema_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("vertical_schemas.id", ondelete="SET NULL")),
    )
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class McpCallLog(SQLModel, table=True):
    __tablename__ = "mcp_call_logs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tool_name: str = Field(index=True, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    result_ids: list[Any] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    agent_name: str = Field(default="", max_length=200)
    user_agent: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    agent_class: str = Field(default="unknown", max_length=80)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )


class PageFetchLog(SQLModel, table=True):
    __tablename__ = "page_fetch_logs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    path: str = Field(sa_column=Column(Text, nullable=False))
    user_agent: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=""))
    agent_class: str = Field(default="unknown", index=True, max_length=80)
    status_code: int = Field(default=200)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
