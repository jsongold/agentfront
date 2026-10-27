"""Initial catalog tables. Vertical fields stay in JSONB."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB
TS = sa.DateTime(timezone=True)


def _id() -> sa.Column:
    return sa.Column("id", UUID, primary_key=True)


def upgrade() -> None:
    op.create_table(
        "vertical_schemas",
        _id(),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("json_schema", JSONB, nullable=False),
        sa.Column("parent_id", UUID, sa.ForeignKey("vertical_schemas.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(32), nullable=False, server_default="proposed"),
        sa.Column("created_at", TS, nullable=False),
        sa.UniqueConstraint("key", "version", name="uq_vertical_schema_version"),
    )
    op.create_index("ix_vertical_schemas_key", "vertical_schemas", ["key"])

    op.create_table(
        "businesses",
        _id(),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("seller", JSONB, nullable=False),
        sa.Column("service_area", JSONB, nullable=False),
        sa.Column("tags", JSONB, nullable=False),
        sa.Column("price_range", JSONB),
        sa.Column("trust", JSONB, nullable=False),
        sa.Column("extension", JSONB, nullable=False),
        sa.Column("images", JSONB, nullable=False),
        sa.Column("source_urls", JSONB, nullable=False),
        sa.Column("source_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("schema_org_type", sa.String(80), nullable=False, server_default="ProfessionalService"),
        sa.Column("vertical_key", sa.String(80)),
        sa.Column("vertical_schema_id", UUID, sa.ForeignKey("vertical_schemas.id", ondelete="SET NULL")),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.Column("published_at", TS),
        sa.UniqueConstraint("slug", name="uq_businesses_slug"),
    )
    op.create_index("ix_businesses_status", "businesses", ["status"])
    op.create_index("ix_businesses_vertical_key", "businesses", ["vertical_key"])

    op.create_table(
        "offerings",
        _id(),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="service"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("price_range", JSONB),
        sa.Column("tags", JSONB, nullable=False),
        sa.Column("area", JSONB, nullable=False),
        sa.Column("images", JSONB, nullable=False),
        sa.Column("extension", JSONB, nullable=False),
        sa.Column("schema_org_type", sa.String(80), nullable=False, server_default="Service"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("business_id", "slug", name="uq_offering_slug"),
    )
    op.create_index("ix_offerings_business_id", "offerings", ["business_id"])

    op.create_table(
        "works",
        _id(),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(160), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("year", sa.Integer()),
        sa.Column("client", sa.String(300)),
        sa.Column("location", sa.String(300)),
        sa.Column("url", sa.Text()),
        sa.Column("images", JSONB, nullable=False),
        sa.Column("extension", JSONB, nullable=False),
        sa.Column("schema_org_type", sa.String(80), nullable=False, server_default="CreativeWork"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("business_id", "slug", name="uq_work_slug"),
    )
    op.create_index("ix_works_business_id", "works", ["business_id"])

    op.create_table(
        "conversion_points",
        _id(),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("offering_id", UUID, sa.ForeignKey("offerings.id", ondelete="SET NULL")),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("input_schema", JSONB, nullable=False),
        sa.Column("external_url", sa.Text()),
        sa.Column("adapters", JSONB, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("business_id", "key", name="uq_conversion_point_key"),
    )
    op.create_index("ix_conversion_points_business_id", "conversion_points", ["business_id"])

    op.create_table(
        "conversions",
        _id(),
        sa.Column("conversion_point_id", UUID, sa.ForeignKey("conversion_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("agent_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("request_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("user_agent", sa.Text(), nullable=False, server_default=""),
        sa.Column("agent_class", sa.String(80), nullable=False, server_default="unknown"),
        sa.Column("status", sa.String(32), nullable=False, server_default="recorded"),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_conversions_created_at", "conversions", ["created_at"])
    op.create_index("ix_conversions_business_id", "conversions", ["business_id"])

    op.create_table(
        "deliveries",
        _id(),
        sa.Column("conversion_id", UUID, sa.ForeignKey("conversions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("adapter_key", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_deliveries_conversion_id", "deliveries", ["conversion_id"])

    op.create_table(
        "generation_runs",
        _id(),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("step", sa.String(40), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text()),
        sa.Column("model", sa.String(120), nullable=False, server_default=""),
        sa.Column("schema_proposal", JSONB),
        sa.Column("extracted", JSONB),
        sa.Column("vertical_schema_id", UUID, sa.ForeignKey("vertical_schemas.id", ondelete="SET NULL")),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("finished_at", TS),
    )
    op.create_index("ix_generation_runs_business_id", "generation_runs", ["business_id"])

    op.create_table(
        "crawl_documents",
        _id(),
        sa.Column("business_id", UUID, sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generation_run_id", UUID, sa.ForeignKey("generation_runs.id", ondelete="CASCADE")),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("title", sa.String(500), nullable=False, server_default=""),
        sa.Column("text", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata_json", JSONB, nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("fetched_at", TS, nullable=False),
    )
    op.create_index("ix_crawl_documents_business_id", "crawl_documents", ["business_id"])

    op.create_table(
        "mcp_call_logs",
        _id(),
        sa.Column("tool_name", sa.String(80), nullable=False),
        sa.Column("arguments", JSONB, nullable=False),
        sa.Column("result_ids", JSONB, nullable=False),
        sa.Column("agent_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("user_agent", sa.Text(), nullable=False, server_default=""),
        sa.Column("agent_class", sa.String(80), nullable=False, server_default="unknown"),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_mcp_call_logs_created_at", "mcp_call_logs", ["created_at"])
    op.create_index("ix_mcp_call_logs_tool_name", "mcp_call_logs", ["tool_name"])

    op.create_table(
        "page_fetch_logs",
        _id(),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=False, server_default=""),
        sa.Column("agent_class", sa.String(80), nullable=False, server_default="unknown"),
        sa.Column("status_code", sa.Integer(), nullable=False, server_default="200"),
        sa.Column("created_at", TS, nullable=False),
    )
    op.create_index("ix_page_fetch_logs_created_at", "page_fetch_logs", ["created_at"])
    op.create_index("ix_page_fetch_logs_agent_class", "page_fetch_logs", ["agent_class"])


def downgrade() -> None:
    for name in (
        "page_fetch_logs",
        "mcp_call_logs",
        "crawl_documents",
        "generation_runs",
        "deliveries",
        "conversions",
        "conversion_points",
        "works",
        "offerings",
        "businesses",
        "vertical_schemas",
    ):
        op.drop_table(name)
