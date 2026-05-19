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
    if "clients" not in inspector.get_table_names():
        return
    client_columns = {column["name"] for column in inspector.get_columns("clients")}
    product_columns = (
        {column["name"] for column in inspector.get_columns("products")}
        if "products" in inspector.get_table_names()
        else set()
    )
    with engine.begin() as connection:
        order_columns = (
            {column["name"] for column in inspector.get_columns("orders")}
            if "orders" in inspector.get_table_names()
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
        }.items():
            if column_name not in product_columns:
                connection.execute(text(f"ALTER TABLE products ADD COLUMN {column_name} {column_type}"))
        if "product_type_export_rules" not in inspector.get_table_names():
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_development_app()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
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
