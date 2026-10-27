"""Store the required-field completeness report on each business."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "002_completeness"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("businesses", sa.Column("completeness", postgresql.JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("businesses", "completeness")
