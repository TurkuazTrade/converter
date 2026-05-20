from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.repositories.users import UserRepository
from app.utils.normalization import normalize_key, normalize_product_type, normalize_text

configure_logging()
settings.ensure_directories()


def bootstrap_development_app() -> None:
    if settings.environment != "development":
        return
    Base.metadata.create_all(bind=engine)
    _ensure_development_columns()
    if not settings.auto_create_admin:
        return
    with SessionLocal() as db:
        users = UserRepository(db)
        users.ensure_user(
            email=settings.default_admin_email,
            password=settings.default_admin_password,
            full_name=settings.default_admin_full_name,
            role="admin",
        )
        users.ensure_user(
            email=settings.default_test_user_email,
            password=settings.default_test_user_password,
            full_name=settings.default_test_user_full_name,
            role="admin",
        )
        db.commit()


def _ensure_development_columns() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "clients" not in table_names:
        return
    client_columns = {column["name"] for column in inspector.get_columns("clients")}
    product_columns = (
        {column["name"] for column in inspector.get_columns("products")}
        if "products" in table_names
        else set()
    )
    with engine.begin() as connection:
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
        if "conversion_multiplier" not in product_columns:
            connection.execute(
                text("ALTER TABLE products ADD COLUMN conversion_multiplier NUMERIC(14, 3) NOT NULL DEFAULT 1")
            )
        if "exclude_from_export" not in product_columns:
            connection.execute(
                text("ALTER TABLE products ADD COLUMN exclude_from_export BOOLEAN NOT NULL DEFAULT 0")
            )
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
            SELECT id, {value_column} AS value
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
        item_id = connection.execute(
            text(
                f"""
                SELECT id
                FROM {table_name}
                WHERE normalized_name = :normalized_name
                  AND deleted_at IS NULL
                LIMIT 1
                """
            ),
            {"normalized_name": normalized_name},
        ).scalar_one_or_none()
        if item_id is None:
            connection.execute(
                text(
                    f"""
                    INSERT INTO {table_name}
                        (name, normalized_name, is_active, created_at, updated_at, deleted_at)
                    VALUES
                        (:name, :normalized_name, :is_active, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL)
                    """
                ),
                {"name": name, "normalized_name": normalized_name, "is_active": True},
            )
            item_id = connection.execute(
                text(f"SELECT id FROM {table_name} WHERE normalized_name = :normalized_name LIMIT 1"),
                {"normalized_name": normalized_name},
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
