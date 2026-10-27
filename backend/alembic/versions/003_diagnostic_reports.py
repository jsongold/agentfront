"""Store recent agent visibility diagnostics."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "003_diagnostic_reports"
down_revision = "002_completeness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("grade", sa.String(4), nullable=False, server_default="E"),
        sa.Column("report", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_diagnostic_reports_created_at", "diagnostic_reports", ["created_at"])


def downgrade() -> None:
    op.drop_table("diagnostic_reports")
