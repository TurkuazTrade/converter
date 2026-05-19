"""add conversion multiplier fields

Revision ID: 0003_conversion_multiplier
Revises: 0002_product_mapping_item_code
Create Date: 2026-05-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_conversion_multiplier"
down_revision = "0002_product_mapping_item_code"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_mappings",
        sa.Column(
            "conversion_multiplier",
            sa.Numeric(14, 3),
            server_default="1",
            nullable=False,
        ),
    )
    op.add_column(
        "order_items",
        sa.Column("source_quantity", sa.Numeric(14, 3), nullable=True),
    )
    op.add_column(
        "order_items",
        sa.Column(
            "conversion_multiplier",
            sa.Numeric(14, 3),
            server_default="1",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("order_items", "conversion_multiplier")
    op.drop_column("order_items", "source_quantity")
    op.drop_column("product_mappings", "conversion_multiplier")
