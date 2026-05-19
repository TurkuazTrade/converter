"""add product type export rules

Revision ID: 0008_product_type_export_rules
Revises: 0007_product_catalog_fields
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_product_type_export_rules"
down_revision = "0007_product_catalog_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_type_export_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_type", sa.String(length=128), nullable=False),
        sa.Column("exclude_from_export", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_type", name="uq_product_type_export_rules_type"),
    )
    op.create_index(op.f("ix_product_type_export_rules_product_type"), "product_type_export_rules", ["product_type"], unique=False)
    op.alter_column("product_type_export_rules", "exclude_from_export", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_product_type_export_rules_product_type"), table_name="product_type_export_rules")
    op.drop_table("product_type_export_rules")
