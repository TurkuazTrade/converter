from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.constants import DEFAULT_BRANCH_ID, DEFAULT_BRANCH_NAME
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.branch import Branch
from app.repositories.users import UserRepository
from app.utils.normalization import normalize_key, normalize_product_type, normalize_search_text, normalize_text

configure_logging()
settings.ensure_directories()

_CLIENT_SEARCH_FIELDS = ("client_code", "name", "name_2", "address", "network_name")
_PRODUCT_SEARCH_FIELDS = (
    "name",
    "item_code",
    "price_code",
    "exchange_code",
    "article",
    "trade_mark",
    "brand",
    "product_type",
)


def bootstrap_development_app() -> None:
    if settings.environment != "development":
        return
    Base.metadata.create_all(bind=engine)
    _ensure_development_columns()
    if not settings.auto_create_admin:
        return
    with SessionLocal() as db:
        branch = db.get(Branch, DEFAULT_BRANCH_ID)
        if branch is None:
            branch = Branch(id=DEFAULT_BRANCH_ID, name=DEFAULT_BRANCH_NAME, is_active=True)
            db.add(branch)
            db.flush()
        users = UserRepository(db)
        users.ensure_user(
            email=settings.default_admin_email,
            password=settings.default_admin_password,
            full_name=settings.default_admin_full_name,
            role="admin",
            branch_id=DEFAULT_BRANCH_ID,
        )
        users.ensure_user(
            email=settings.default_test_user_email,
            password=settings.default_test_user_password,
            full_name=settings.default_test_user_full_name,
            role="admin",
            branch_id=DEFAULT_BRANCH_ID,
        )
        db.commit()


def _ensure_development_columns() -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        table_names = set(inspector.get_table_names())
        if "branches" not in table_names:
            Base.metadata.tables["branches"].create(bind=connection)
            table_names.add("branches")
        connection.execute(
            text(
                """
                INSERT OR IGNORE INTO branches
                    (id, name, code, is_active, created_at, updated_at, deleted_at)
                VALUES
                    (:id, :name, NULL, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL)
                """
            ),
            {"id": DEFAULT_BRANCH_ID, "name": DEFAULT_BRANCH_NAME},
        )
        if "clients" not in table_names:
            return
        client_columns = {column["name"] for column in inspector.get_columns("clients")}
        product_columns = (
            {column["name"] for column in inspector.get_columns("products")}
            if "products" in table_names
            else set()
        )
        for table_name in (
            "users",
            "clients",
            "products",
            "product_mappings",
            "client_mappings",
            "orders",
            "files",
            "product_brands",
            "product_trade_marks",
            "product_types",
            "product_type_export_rules",
        ):
            if table_name in table_names:
                _ensure_development_branch_column(connection, inspector, table_name)
        order_columns = (
            {column["name"] for column in inspector.get_columns("orders")}
            if "orders" in table_names
            else set()
        )
        if "export_downloaded_at" not in order_columns:
            connection.execute(text("ALTER TABLE orders ADD COLUMN export_downloaded_at DATETIME"))
        if "export_downloads" not in order_columns:
            connection.execute(text("ALTER TABLE orders ADD COLUMN export_downloads JSON"))
        if "name_2" not in client_columns:
            connection.execute(text("ALTER TABLE clients ADD COLUMN name_2 VARCHAR(512)"))
            client_columns.add("name_2")
        if "search_text" not in client_columns:
            connection.execute(text("ALTER TABLE clients ADD COLUMN search_text VARCHAR(2048) NOT NULL DEFAULT ''"))
            client_columns.add("search_text")
        if "conversion_multiplier" not in product_columns:
            connection.execute(
                text("ALTER TABLE products ADD COLUMN conversion_multiplier NUMERIC(14, 3) NOT NULL DEFAULT 1")
            )
            product_columns.add("conversion_multiplier")
        if "exclude_from_export" not in product_columns:
            connection.execute(
                text("ALTER TABLE products ADD COLUMN exclude_from_export BOOLEAN NOT NULL DEFAULT 0")
            )
            product_columns.add("exclude_from_export")
        if "search_text" not in product_columns:
            connection.execute(text("ALTER TABLE products ADD COLUMN search_text VARCHAR(2048) NOT NULL DEFAULT ''"))
            product_columns.add("search_text")
        for column_name, column_type in {
            "exchange_code": "VARCHAR(128)",
            "article": "VARCHAR(128)",
            "stock": "VARCHAR(128)",
            "trade_mark": "VARCHAR(256)",
            "brand": "VARCHAR(256)",
            "product_type": "VARCHAR(128)",
            "trade_mark_id": "INTEGER",
            "brand_id": "INTEGER",
            "product_type_id": "INTEGER",
        }.items():
            if column_name not in product_columns:
                connection.execute(text(f"ALTER TABLE products ADD COLUMN {column_name} {column_type}"))
                product_columns.add(column_name)
        for table_name in ("product_brands", "product_trade_marks", "product_types", "product_type_export_rules"):
            if table_name not in table_names:
                Base.metadata.tables[table_name].create(bind=connection)
                table_names.add(table_name)
        product_type_columns = (
            {column["name"] for column in inspector.get_columns("product_types")}
            if "product_types" in inspector.get_table_names()
            else set()
        )
        if "product_types" in inspector.get_table_names() and "warehouse_no" not in product_type_columns:
            connection.execute(text("ALTER TABLE product_types ADD COLUMN warehouse_no VARCHAR(64)"))
        if "product_type_export_rules" not in table_names:
            Base.metadata.tables["product_type_export_rules"].create(bind=connection)
        if "product_type" in product_columns:
            connection.execute(
                text(
                    """
                    UPDATE products
                    SET product_type = lower(trim(product_type))
                    WHERE product_type IS NOT NULL
                      AND product_type != lower(trim(product_type))
                    """
                )
            )
        if "product_type_export_rules" in inspector.get_table_names():
            connection.execute(
                text(
                    """
                    UPDATE product_type_export_rules
                    SET product_type = lower(trim(product_type))
                    WHERE product_type IS NOT NULL
                      AND product_type != lower(trim(product_type))
                    """
                )
            )
        if {"brand", "brand_id"}.issubset(product_columns):
            _backfill_development_product_dictionary(
                connection,
                table_name="product_brands",
                value_column="brand",
                id_column="brand_id",
            )
        if {"trade_mark", "trade_mark_id"}.issubset(product_columns):
            _backfill_development_product_dictionary(
                connection,
                table_name="product_trade_marks",
                value_column="trade_mark",
                id_column="trade_mark_id",
            )
        if {"product_type", "product_type_id"}.issubset(product_columns):
            _backfill_development_product_dictionary(
                connection,
                table_name="product_types",
                value_column="product_type",
                id_column="product_type_id",
                normalize_as_type=True,
            )
        if "product_mappings" in inspector.get_table_names():
            connection.execute(
                text(
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
                    WHERE conversion_multiplier = 1
                      AND EXISTS (
                        SELECT 1
                        FROM product_mappings
                        WHERE product_mappings.product_id = products.id
                          AND product_mappings.deleted_at IS NULL
                          AND product_mappings.conversion_multiplier > 0
                      )
                    """
                )
            )
        _backfill_development_search_text(connection, "clients", _CLIENT_SEARCH_FIELDS)
        _backfill_development_search_text(connection, "products", _PRODUCT_SEARCH_FIELDS)
        _ensure_development_indexes(connection, table_names)


def _ensure_development_branch_column(connection, inspector, table_name: str) -> None:
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if "branch_id" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN branch_id INTEGER"))
    connection.execute(
        text(f"UPDATE {table_name} SET branch_id = :branch_id WHERE branch_id IS NULL"),
        {"branch_id": DEFAULT_BRANCH_ID},
    )


def _backfill_development_search_text(connection, table_name: str, fields: tuple[str, ...]) -> None:
    rows = connection.execute(
        text(
            f"""
            SELECT id, {", ".join(fields)}
            FROM {table_name}
            WHERE search_text IS NULL OR search_text = ''
            """
        )
    )
    for row in rows:
        values = row._mapping
        connection.execute(
            text(f"UPDATE {table_name} SET search_text = :search_text WHERE id = :id"),
            {
                "id": values["id"],
                "search_text": normalize_search_text(*(values[field] for field in fields)),
            },
        )


def _ensure_development_indexes(connection, table_names: set[str]) -> None:
    if "products" in table_names:
        _ensure_development_index(connection, "products", "ix_products_branch_id", ("branch_id",))
        _ensure_development_index(connection, "products", "ix_products_branch_name", ("branch_id", "name"))
        _ensure_development_index(
            connection,
            "products",
            "ix_products_branch_deleted_name",
            ("branch_id", "deleted_at", "name"),
        )
        _ensure_development_index(connection, "products", "ix_products_branch_search", ("branch_id", "search_text"))
        _ensure_development_index(connection, "products", "ix_products_branch_brand", ("branch_id", "brand"))
        _ensure_development_index(
            connection,
            "products",
            "ix_products_branch_trade_mark",
            ("branch_id", "trade_mark"),
        )
        _ensure_development_index(
            connection,
            "products",
            "ix_products_branch_product_type",
            ("branch_id", "product_type"),
        )
        _ensure_development_index(
            connection,
            "products",
            "ix_products_branch_created_at",
            ("branch_id", "created_at"),
        )
    if "clients" in table_names:
        _ensure_development_index(connection, "clients", "ix_clients_branch_id", ("branch_id",))
        _ensure_development_index(connection, "clients", "ix_clients_branch_name", ("branch_id", "name"))
        _ensure_development_index(
            connection,
            "clients",
            "ix_clients_branch_active_name",
            ("branch_id", "deleted_at", "is_active", "name"),
        )
        _ensure_development_index(connection, "clients", "ix_clients_branch_search", ("branch_id", "search_text"))
        _ensure_development_index(
            connection,
            "clients",
            "ix_clients_network_address",
            ("branch_id", "network_name", "normalized_address"),
        )
    if "orders" in table_names:
        _ensure_development_index(connection, "orders", "ix_orders_branch_id", ("branch_id",))
        _ensure_development_index(
            connection,
            "orders",
            "ix_orders_branch_status_created",
            ("branch_id", "status", "created_at"),
        )
        _ensure_development_index(
            connection,
            "orders",
            "ix_orders_branch_created_at",
            ("branch_id", "created_at"),
        )
    if "product_mappings" in table_names:
        _ensure_development_index(connection, "product_mappings", "ix_product_mappings_branch_id", ("branch_id",))
        _ensure_development_index(
            connection,
            "product_mappings",
            "ix_product_mappings_branch_barcode",
            ("branch_id", "converter_type", "normalized_barcode"),
        )
        _ensure_development_index(
            connection,
            "product_mappings",
            "ix_product_mappings_branch_item_code",
            ("branch_id", "converter_type", "normalized_item_code"),
        )
        _ensure_development_index(
            connection,
            "product_mappings",
            "ix_product_mappings_branch_name",
            ("branch_id", "converter_type", "normalized_name"),
        )
    if "client_mappings" in table_names:
        _ensure_development_index(connection, "client_mappings", "ix_client_mappings_branch_id", ("branch_id",))
        _ensure_development_index(
            connection,
            "client_mappings",
            "ix_client_mappings_branch_name",
            ("branch_id", "converter_type", "normalized_client_name"),
        )
        _ensure_development_index(
            connection,
            "client_mappings",
            "ix_client_mappings_branch_address",
            ("branch_id", "converter_type", "normalized_address"),
        )


def _ensure_development_index(
    connection,
    table_name: str,
    index_name: str,
    columns: tuple[str, ...],
) -> None:
    existing_columns = _development_index_columns(connection, index_name)
    if existing_columns and existing_columns != columns:
        connection.execute(text(f"DROP INDEX {index_name}"))
    connection.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({', '.join(columns)})"))


def _development_index_columns(connection, index_name: str) -> tuple[str, ...] | None:
    rows = connection.execute(text(f"PRAGMA index_info({index_name})"))
    columns = tuple(row._mapping["name"] for row in rows)
    return columns or None


def _backfill_development_product_dictionary(
    connection,
    *,
    table_name: str,
    value_column: str,
    id_column: str,
    normalize_as_type: bool = False,
) -> None:
    rows = connection.execute(
        text(
            f"""
            SELECT id, branch_id, {value_column} AS value
            FROM products
            WHERE deleted_at IS NULL
              AND {value_column} IS NOT NULL
              AND trim({value_column}) != ''
            """
        )
    )
    for row in rows:
        value = row._mapping["value"]
        name = normalize_product_type(value) if normalize_as_type else normalize_text(value)
        if not name:
            continue
        normalized_name = name if normalize_as_type else normalize_key(name)
        if not normalized_name:
            continue
        branch_id = row._mapping["branch_id"] or DEFAULT_BRANCH_ID
        item_id = connection.execute(
            text(
                f"""
                SELECT id
                FROM {table_name}
                WHERE normalized_name = :normalized_name
                  AND branch_id = :branch_id
                  AND deleted_at IS NULL
                LIMIT 1
                """
            ),
            {"normalized_name": normalized_name, "branch_id": branch_id},
        ).scalar_one_or_none()
        if item_id is None:
            connection.execute(
                text(
                    f"""
                    INSERT INTO {table_name}
                        (name, normalized_name, branch_id, is_active, created_at, updated_at, deleted_at)
                    VALUES
                        (:name, :normalized_name, :branch_id, :is_active, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL)
                    """
                ),
                {"name": name, "normalized_name": normalized_name, "branch_id": branch_id, "is_active": True},
            )
            item_id = connection.execute(
                text(
                    f"""
                    SELECT id
                    FROM {table_name}
                    WHERE normalized_name = :normalized_name
                      AND branch_id = :branch_id
                    LIMIT 1
                    """
                ),
                {"normalized_name": normalized_name, "branch_id": branch_id},
            ).scalar_one()
        connection.execute(
            text(
                f"""
                UPDATE products
                SET {id_column} = :item_id,
                    {value_column} = :name
                WHERE id = :product_id
                """
            ),
            {"item_id": item_id, "name": name, "product_id": row._mapping["id"]},
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_development_app()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_origin_regex=settings.backend_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "Content-Disposition",
        "X-Export-Previously-Downloaded-By",
        "X-Export-Previously-Downloaded-At",
    ],
)

app.include_router(api_router)
