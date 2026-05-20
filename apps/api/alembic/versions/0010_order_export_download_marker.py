"""add order export download marker

Revision ID: 0010_order_export_download_marker
Revises: 0009_normalize_product_types
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_order_export_download_marker"
down_revision = "0009_normalize_product_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("export_downloaded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("export_downloads", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "export_downloads")
    op.drop_column("orders", "export_downloaded_at")
