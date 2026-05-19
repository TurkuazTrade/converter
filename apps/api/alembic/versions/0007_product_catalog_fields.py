"""add product catalog fields

Revision ID: 0007_product_catalog_fields
Revises: 0006_product_export_exclusion
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_product_catalog_fields"
down_revision = "0006_product_export_exclusion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("exchange_code", sa.String(length=128), nullable=True))
    op.add_column("products", sa.Column("article", sa.String(length=128), nullable=True))
    op.add_column("products", sa.Column("stock", sa.String(length=128), nullable=True))
    op.add_column("products", sa.Column("trade_mark", sa.String(length=256), nullable=True))
    op.add_column("products", sa.Column("brand", sa.String(length=256), nullable=True))
    op.add_column("products", sa.Column("product_type", sa.String(length=128), nullable=True))
    op.create_index(op.f("ix_products_exchange_code"), "products", ["exchange_code"], unique=False)
    op.create_index(op.f("ix_products_article"), "products", ["article"], unique=False)
    op.create_index(op.f("ix_products_trade_mark"), "products", ["trade_mark"], unique=False)
    op.create_index(op.f("ix_products_brand"), "products", ["brand"], unique=False)
    op.create_index(op.f("ix_products_product_type"), "products", ["product_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_products_product_type"), table_name="products")
    op.drop_index(op.f("ix_products_brand"), table_name="products")
    op.drop_index(op.f("ix_products_trade_mark"), table_name="products")
    op.drop_index(op.f("ix_products_article"), table_name="products")
    op.drop_index(op.f("ix_products_exchange_code"), table_name="products")
    op.drop_column("products", "product_type")
    op.drop_column("products", "brand")
    op.drop_column("products", "trade_mark")
    op.drop_column("products", "stock")
    op.drop_column("products", "article")
    op.drop_column("products", "exchange_code")
