"""add branch scoping

Revision ID: 0015_branch_scoping
Revises: 0014_app_settings
Create Date: 2026-05-30
"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0015_branch_scoping"
down_revision = "0014_app_settings"
branch_labels = None
depends_on = None

DEFAULT_BRANCH_ID = 1
DEFAULT_BRANCH_NAME = "Основной филиал"


def upgrade() -> None:
    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_branches_code"), "branches", ["code"], unique=True)

    now = datetime.now(timezone.utc)
    op.bulk_insert(
        sa.table(
            "branches",
            sa.column("id", sa.Integer()),
            sa.column("name", sa.String()),
            sa.column("code", sa.String()),
            sa.column("is_active", sa.Boolean()),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
            sa.column("deleted_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": DEFAULT_BRANCH_ID,
                "name": DEFAULT_BRANCH_NAME,
                "code": None,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            }
        ],
    )

    _add_branch_column("users", "fk_users_branch_id_branches")
    _add_branch_column("files", "fk_files_branch_id_branches")

    with op.batch_alter_table("clients") as batch_op:
        batch_op.add_column(sa.Column("branch_id", sa.Integer(), nullable=True))
        batch_op.drop_constraint("uq_clients_client_code", type_="unique")
        batch_op.create_foreign_key("fk_clients_branch_id_branches", "branches", ["branch_id"], ["id"])
        batch_op.create_index(op.f("ix_clients_branch_id"), ["branch_id"], unique=False)
        batch_op.create_unique_constraint("uq_clients_branch_client_code", ["branch_id", "client_code"])

    with op.batch_alter_table("products") as batch_op:
        batch_op.add_column(sa.Column("branch_id", sa.Integer(), nullable=True))
        batch_op.drop_index(op.f("ix_products_item_code"))
        batch_op.create_index(op.f("ix_products_item_code"), ["item_code"], unique=False)
        batch_op.create_foreign_key("fk_products_branch_id_branches", "branches", ["branch_id"], ["id"])
        batch_op.create_index(op.f("ix_products_branch_id"), ["branch_id"], unique=False)
        batch_op.create_unique_constraint("uq_products_branch_item_code", ["branch_id", "item_code"])

    op.create_index("ix_products_branch_name", "products", ["branch_id", "name"], unique=False)

    with op.batch_alter_table("product_brands") as batch_op:
        batch_op.add_column(sa.Column("branch_id", sa.Integer(), nullable=True))
        batch_op.drop_constraint("uq_product_brands_normalized_name", type_="unique")
        batch_op.create_foreign_key("fk_product_brands_branch_id_branches", "branches", ["branch_id"], ["id"])
        batch_op.create_index(op.f("ix_product_brands_branch_id"), ["branch_id"], unique=False)
        batch_op.create_unique_constraint("uq_product_brands_branch_normalized_name", ["branch_id", "normalized_name"])

    with op.batch_alter_table("product_trade_marks") as batch_op:
        batch_op.add_column(sa.Column("branch_id", sa.Integer(), nullable=True))
        batch_op.drop_constraint("uq_product_trade_marks_normalized_name", type_="unique")
        batch_op.create_foreign_key("fk_product_trade_marks_branch_id_branches", "branches", ["branch_id"], ["id"])
        batch_op.create_index(op.f("ix_product_trade_marks_branch_id"), ["branch_id"], unique=False)
        batch_op.create_unique_constraint(
            "uq_product_trade_marks_branch_normalized_name",
            ["branch_id", "normalized_name"],
        )

    with op.batch_alter_table("product_types") as batch_op:
        batch_op.add_column(sa.Column("branch_id", sa.Integer(), nullable=True))
        batch_op.drop_constraint("uq_product_types_normalized_name", type_="unique")
        batch_op.create_foreign_key("fk_product_types_branch_id_branches", "branches", ["branch_id"], ["id"])
        batch_op.create_index(op.f("ix_product_types_branch_id"), ["branch_id"], unique=False)
        batch_op.create_unique_constraint("uq_product_types_branch_normalized_name", ["branch_id", "normalized_name"])

    with op.batch_alter_table("product_type_export_rules") as batch_op:
        batch_op.add_column(sa.Column("branch_id", sa.Integer(), nullable=True))
        batch_op.drop_constraint("uq_product_type_export_rules_type", type_="unique")
        batch_op.create_foreign_key("fk_product_type_export_rules_branch_id_branches", "branches", ["branch_id"], ["id"])
        batch_op.create_index(op.f("ix_product_type_export_rules_branch_id"), ["branch_id"], unique=False)
        batch_op.create_unique_constraint("uq_product_type_export_rules_branch_type", ["branch_id", "product_type"])

    _add_branch_column("orders", "fk_orders_branch_id_branches")
    _add_branch_column("product_mappings", "fk_product_mappings_branch_id_branches")
    _add_branch_column("client_mappings", "fk_client_mappings_branch_id_branches")

    for table_name in (
        "users",
        "files",
        "clients",
        "products",
        "product_brands",
        "product_trade_marks",
        "product_types",
        "product_type_export_rules",
        "orders",
        "product_mappings",
        "client_mappings",
    ):
        op.execute(
            sa.text(f"UPDATE {table_name} SET branch_id = :branch_id WHERE branch_id IS NULL").bindparams(
                branch_id=DEFAULT_BRANCH_ID
            )
        )

    op.create_index(
        "ix_product_mappings_branch_barcode",
        "product_mappings",
        ["branch_id", "converter_type", "normalized_barcode"],
        unique=False,
    )
    op.create_index(
        "ix_product_mappings_branch_item_code",
        "product_mappings",
        ["branch_id", "converter_type", "normalized_item_code"],
        unique=False,
    )
    op.create_index(
        "ix_product_mappings_branch_name",
        "product_mappings",
        ["branch_id", "converter_type", "normalized_name"],
        unique=False,
    )
    op.create_index(
        "ix_client_mappings_branch_name",
        "client_mappings",
        ["branch_id", "converter_type", "normalized_client_name"],
        unique=False,
    )
    op.create_index(
        "ix_client_mappings_branch_address",
        "client_mappings",
        ["branch_id", "converter_type", "normalized_address"],
        unique=False,
    )
    op.create_index("ix_orders_branch_status_created", "orders", ["branch_id", "status", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_orders_branch_status_created", table_name="orders")
    op.drop_index("ix_client_mappings_branch_address", table_name="client_mappings")
    op.drop_index("ix_client_mappings_branch_name", table_name="client_mappings")
    op.drop_index("ix_product_mappings_branch_name", table_name="product_mappings")
    op.drop_index("ix_product_mappings_branch_item_code", table_name="product_mappings")
    op.drop_index("ix_product_mappings_branch_barcode", table_name="product_mappings")
    op.drop_index("ix_products_branch_name", table_name="products")

    _drop_branch_column("client_mappings", "fk_client_mappings_branch_id_branches")
    _drop_branch_column("product_mappings", "fk_product_mappings_branch_id_branches")
    _drop_branch_column("orders", "fk_orders_branch_id_branches")

    with op.batch_alter_table("product_type_export_rules") as batch_op:
        batch_op.drop_constraint("uq_product_type_export_rules_branch_type", type_="unique")
        batch_op.drop_index(op.f("ix_product_type_export_rules_branch_id"))
        batch_op.drop_constraint("fk_product_type_export_rules_branch_id_branches", type_="foreignkey")
        batch_op.drop_column("branch_id")
        batch_op.create_unique_constraint("uq_product_type_export_rules_type", ["product_type"])

    with op.batch_alter_table("product_types") as batch_op:
        batch_op.drop_constraint("uq_product_types_branch_normalized_name", type_="unique")
        batch_op.drop_index(op.f("ix_product_types_branch_id"))
        batch_op.drop_constraint("fk_product_types_branch_id_branches", type_="foreignkey")
        batch_op.drop_column("branch_id")
        batch_op.create_unique_constraint("uq_product_types_normalized_name", ["normalized_name"])

    with op.batch_alter_table("product_trade_marks") as batch_op:
        batch_op.drop_constraint("uq_product_trade_marks_branch_normalized_name", type_="unique")
        batch_op.drop_index(op.f("ix_product_trade_marks_branch_id"))
        batch_op.drop_constraint("fk_product_trade_marks_branch_id_branches", type_="foreignkey")
        batch_op.drop_column("branch_id")
        batch_op.create_unique_constraint("uq_product_trade_marks_normalized_name", ["normalized_name"])

    with op.batch_alter_table("product_brands") as batch_op:
        batch_op.drop_constraint("uq_product_brands_branch_normalized_name", type_="unique")
        batch_op.drop_index(op.f("ix_product_brands_branch_id"))
        batch_op.drop_constraint("fk_product_brands_branch_id_branches", type_="foreignkey")
        batch_op.drop_column("branch_id")
        batch_op.create_unique_constraint("uq_product_brands_normalized_name", ["normalized_name"])

    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_constraint("uq_products_branch_item_code", type_="unique")
        batch_op.drop_index(op.f("ix_products_branch_id"))
        batch_op.drop_constraint("fk_products_branch_id_branches", type_="foreignkey")
        batch_op.drop_index(op.f("ix_products_item_code"))
        batch_op.create_index(op.f("ix_products_item_code"), ["item_code"], unique=True)
        batch_op.drop_column("branch_id")

    with op.batch_alter_table("clients") as batch_op:
        batch_op.drop_constraint("uq_clients_branch_client_code", type_="unique")
        batch_op.drop_index(op.f("ix_clients_branch_id"))
        batch_op.drop_constraint("fk_clients_branch_id_branches", type_="foreignkey")
        batch_op.drop_column("branch_id")
        batch_op.create_unique_constraint("uq_clients_client_code", ["client_code"])

    _drop_branch_column("files", "fk_files_branch_id_branches")
    _drop_branch_column("users", "fk_users_branch_id_branches")

    op.drop_index(op.f("ix_branches_code"), table_name="branches")
    op.drop_table("branches")


def _add_branch_column(table_name: str, fk_name: str) -> None:
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.add_column(sa.Column("branch_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(fk_name, "branches", ["branch_id"], ["id"])
        batch_op.create_index(op.f(f"ix_{table_name}_branch_id"), ["branch_id"], unique=False)


def _drop_branch_column(table_name: str, fk_name: str) -> None:
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_index(op.f(f"ix_{table_name}_branch_id"))
        batch_op.drop_constraint(fk_name, type_="foreignkey")
        batch_op.drop_column("branch_id")
