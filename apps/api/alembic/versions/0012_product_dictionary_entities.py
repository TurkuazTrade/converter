"""add product dictionary entities

Revision ID: 0012_product_dictionary_entities
Revises: 0011_remove_client_code_2
Create Date: 2026-05-19
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "0012_product_dictionary_entities"
down_revision = "0011_remove_client_code_2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _create_dictionary_table(
        "product_brands",
        "uq_product_brands_normalized_name",
        name_length=256,
    )
    _create_dictionary_table(
        "product_trade_marks",
        "uq_product_trade_marks_normalized_name",
        name_length=256,
    )
    _create_dictionary_table(
        "product_types",
        "uq_product_types_normalized_name",
        name_length=128,
    )

    with op.batch_alter_table("products") as batch_op:
        batch_op.add_column(sa.Column("trade_mark_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("brand_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("product_type_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_products_trade_mark_id_product_trade_marks",
            "product_trade_marks",
            ["trade_mark_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_products_brand_id_product_brands",
            "product_brands",
            ["brand_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_products_product_type_id_product_types",
            "product_types",
            ["product_type_id"],
            ["id"],
        )
        batch_op.create_index(op.f("ix_products_trade_mark_id"), ["trade_mark_id"], unique=False)
        batch_op.create_index(op.f("ix_products_brand_id"), ["brand_id"], unique=False)
        batch_op.create_index(op.f("ix_products_product_type_id"), ["product_type_id"], unique=False)

    connection = op.get_bind()
    _backfill_dictionary(
        connection,
        table_name="product_brands",
        value_column="brand",
        id_column="brand_id",
    )
    _backfill_dictionary(
        connection,
        table_name="product_trade_marks",
        value_column="trade_mark",
        id_column="trade_mark_id",
    )
    _backfill_dictionary(
        connection,
        table_name="product_types",
        value_column="product_type",
        id_column="product_type_id",
        normalize_as_type=True,
    )


def downgrade() -> None:
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_index(op.f("ix_products_product_type_id"))
        batch_op.drop_index(op.f("ix_products_brand_id"))
        batch_op.drop_index(op.f("ix_products_trade_mark_id"))
        batch_op.drop_constraint("fk_products_product_type_id_product_types", type_="foreignkey")
        batch_op.drop_constraint("fk_products_brand_id_product_brands", type_="foreignkey")
        batch_op.drop_constraint("fk_products_trade_mark_id_product_trade_marks", type_="foreignkey")
        batch_op.drop_column("product_type_id")
        batch_op.drop_column("brand_id")
        batch_op.drop_column("trade_mark_id")
    op.drop_table("product_types")
    op.drop_table("product_trade_marks")
    op.drop_table("product_brands")


def _create_dictionary_table(table_name: str, unique_name: str, *, name_length: int) -> None:
    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=name_length), nullable=False),
        sa.Column("normalized_name", sa.String(length=name_length), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_name", name=unique_name),
    )
    op.create_index(op.f(f"ix_{table_name}_normalized_name"), table_name, ["normalized_name"], unique=False)


def _backfill_dictionary(
    connection,
    *,
    table_name: str,
    value_column: str,
    id_column: str,
    normalize_as_type: bool = False,
) -> None:
    products = sa.table(
        "products",
        sa.column("id", sa.Integer()),
        sa.column(value_column, sa.String()),
        sa.column(id_column, sa.Integer()),
    )
    dictionary = sa.table(
        table_name,
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("normalized_name", sa.String()),
        sa.column("is_active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
    )
    rows = connection.execute(
        sa.select(products.c.id, products.c[value_column]).where(
            products.c[value_column].is_not(None),
            products.c[value_column] != "",
        )
    )
    for product_id, raw_value in rows:
        name = _normalize_product_type(raw_value) if normalize_as_type else _normalize_text(raw_value)
        if not name:
            continue
        normalized_name = name if normalize_as_type else _normalize_key(name)
        if not normalized_name:
            continue
        dictionary_id = connection.execute(
            sa.select(dictionary.c.id).where(dictionary.c.normalized_name == normalized_name)
        ).scalar_one_or_none()
        if dictionary_id is None:
            now = datetime.now(timezone.utc)
            connection.execute(
                dictionary.insert().values(
                    name=name,
                    normalized_name=normalized_name,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                    deleted_at=None,
                )
            )
            dictionary_id = connection.execute(
                sa.select(dictionary.c.id).where(dictionary.c.normalized_name == normalized_name)
            ).scalar_one()
        connection.execute(
            products.update()
            .where(products.c.id == product_id)
            .values({id_column: dictionary_id, value_column: name})
        )


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u00a0", " ").strip()
    return re.sub(r"\s+", " ", text)


def _normalize_key(value: Any) -> str:
    text = _normalize_text(value).casefold().replace("ё", "е")
    return re.sub(r"[^0-9a-zа-я]+", "", text)


def _normalize_product_type(value: Any) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None
    return text.casefold()
