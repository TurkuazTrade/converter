"""normalize product type values

Revision ID: 0009_normalize_product_types
Revises: 0008_product_type_export_rules
Create Date: 2026-05-19
"""

from __future__ import annotations

from alembic import op

revision = "0009_normalize_product_types"
down_revision = "0008_product_type_export_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE products
        SET product_type = lower(trim(product_type))
        WHERE product_type IS NOT NULL
          AND product_type != lower(trim(product_type))
        """
    )
    op.execute(
        """
        UPDATE product_type_export_rules
        SET product_type = lower(trim(product_type))
        WHERE product_type IS NOT NULL
          AND product_type != lower(trim(product_type))
        """
    )


def downgrade() -> None:
    pass
