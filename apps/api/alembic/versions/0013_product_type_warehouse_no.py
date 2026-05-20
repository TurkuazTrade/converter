"""add product type warehouse number

Revision ID: 0013_product_type_warehouse_no
Revises: 0012_product_dictionary_entities
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_product_type_warehouse_no"
down_revision = "0012_product_dictionary_entities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_types", sa.Column("warehouse_no", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("product_types", "warehouse_no")
