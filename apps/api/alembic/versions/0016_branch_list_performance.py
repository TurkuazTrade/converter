"""optimize branch scoped list queries

Revision ID: 0016_branch_list_performance
Revises: 0015_branch_scoping
Create Date: 2026-06-01
"""

from __future__ import annotations

import re
from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "0016_branch_list_performance"
down_revision = "0015_branch_scoping"
branch_labels = None
depends_on = None

CLIENT_SEARCH_FIELDS = ("client_code", "name", "name_2", "address", "network_name")
PRODUCT_SEARCH_FIELDS = (
    "name",
    "item_code",
    "price_code",
    "exchange_code",
    "article",
    "trade_mark",
    "brand",
    "product_type",
)


def upgrade() -> None:
    with op.batch_alter_table("clients") as batch_op:
        batch_op.add_column(sa.Column("search_text", sa.String(length=2048), nullable=False, server_default=""))
        batch_op.drop_index("ix_clients_network_address")
        batch_op.create_index(
            "ix_clients_network_address",
            ["branch_id", "network_name", "normalized_address"],
            unique=False,
        )
        batch_op.create_index("ix_clients_branch_name", ["branch_id", "name"], unique=False)
        batch_op.create_index(
            "ix_clients_branch_active_name",
            ["branch_id", "deleted_at", "is_active", "name"],
            unique=False,
        )
        batch_op.create_index("ix_clients_branch_search", ["branch_id", "search_text"], unique=False)

    with op.batch_alter_table("products") as batch_op:
        batch_op.add_column(sa.Column("search_text", sa.String(length=2048), nullable=False, server_default=""))
        batch_op.create_index(
            "ix_products_branch_deleted_name",
            ["branch_id", "deleted_at", "name"],
            unique=False,
        )
        batch_op.create_index("ix_products_branch_search", ["branch_id", "search_text"], unique=False)
        batch_op.create_index("ix_products_branch_brand", ["branch_id", "brand"], unique=False)
        batch_op.create_index("ix_products_branch_trade_mark", ["branch_id", "trade_mark"], unique=False)
        batch_op.create_index("ix_products_branch_product_type", ["branch_id", "product_type"], unique=False)
        batch_op.create_index("ix_products_branch_created_at", ["branch_id", "created_at"], unique=False)

    op.create_index("ix_orders_branch_created_at", "orders", ["branch_id", "created_at"], unique=False)

    connection = op.get_bind()
    _backfill_search_text(connection, "clients", CLIENT_SEARCH_FIELDS)
    _backfill_search_text(connection, "products", PRODUCT_SEARCH_FIELDS)


def downgrade() -> None:
    op.drop_index("ix_orders_branch_created_at", table_name="orders")

    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_index("ix_products_branch_created_at")
        batch_op.drop_index("ix_products_branch_product_type")
        batch_op.drop_index("ix_products_branch_trade_mark")
        batch_op.drop_index("ix_products_branch_brand")
        batch_op.drop_index("ix_products_branch_search")
        batch_op.drop_index("ix_products_branch_deleted_name")
        batch_op.drop_column("search_text")

    with op.batch_alter_table("clients") as batch_op:
        batch_op.drop_index("ix_clients_branch_search")
        batch_op.drop_index("ix_clients_branch_active_name")
        batch_op.drop_index("ix_clients_branch_name")
        batch_op.drop_index("ix_clients_network_address")
        batch_op.create_index("ix_clients_network_address", ["network_name", "normalized_address"], unique=False)
        batch_op.drop_column("search_text")


def _backfill_search_text(connection, table_name: str, fields: tuple[str, ...]) -> None:
    rows = connection.execute(sa.text(f"SELECT id, {', '.join(fields)} FROM {table_name}"))
    for row in rows:
        values = row._mapping
        connection.execute(
            sa.text(f"UPDATE {table_name} SET search_text = :search_text WHERE id = :id"),
            {
                "id": values["id"],
                "search_text": _normalize_search_text(*(values[field] for field in fields)),
            },
        )


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u00a0", " ").strip()
    return re.sub(r"\s+", " ", text)


def _normalize_key(value: Any) -> str:
    text = _normalize_text(value).casefold().replace("ё", "е")
    return re.sub(r"[^0-9a-zа-я]+", "", text)


def _normalize_search_text(*values: Any) -> str:
    return _normalize_key(" ".join(_normalize_text(value) for value in values if value is not None))
