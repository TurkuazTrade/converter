"""add item-code matching to product mappings

Revision ID: 0002_product_mapping_item_code
Revises: 0001_initial_foundation
Create Date: 2026-05-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_product_mapping_item_code"
down_revision = "0001_initial_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_mappings", sa.Column("raw_item_code", sa.String(length=128), nullable=True))
    op.add_column(
        "product_mappings",
        sa.Column("normalized_item_code", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_product_mappings_raw_item_code",
        "product_mappings",
        ["raw_item_code"],
        unique=False,
    )
    op.create_index(
        "ix_product_mappings_normalized_item_code",
        "product_mappings",
        ["normalized_item_code"],
        unique=False,
    )
    op.create_index(
        "ix_product_mappings_item_code",
        "product_mappings",
        ["converter_type", "normalized_item_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_product_mappings_item_code", table_name="product_mappings")
    op.drop_index("ix_product_mappings_normalized_item_code", table_name="product_mappings")
    op.drop_index("ix_product_mappings_raw_item_code", table_name="product_mappings")
    op.drop_column("product_mappings", "normalized_item_code")
    op.drop_column("product_mappings", "raw_item_code")
