"""add product conversion multiplier

Revision ID: 0005_product_conversion_multiplier
Revises: 0004_client_second_name
Create Date: 2026-05-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_product_conversion_multiplier"
down_revision = "0004_client_second_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "conversion_multiplier",
            sa.Numeric(14, 3),
            nullable=False,
            server_default="1",
        ),
    )
    op.execute(
        """
        UPDATE products
        SET conversion_multiplier = (
            SELECT product_mappings.conversion_multiplier
            FROM product_mappings
            WHERE product_mappings.product_id = products.id
              AND product_mappings.deleted_at IS NULL
              AND product_mappings.conversion_multiplier > 0
            ORDER BY product_mappings.updated_at DESC
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1
            FROM product_mappings
            WHERE product_mappings.product_id = products.id
              AND product_mappings.deleted_at IS NULL
              AND product_mappings.conversion_multiplier > 0
        )
        """
    )
    op.alter_column("products", "conversion_multiplier", server_default=None)


def downgrade() -> None:
    op.drop_column("products", "conversion_multiplier")
