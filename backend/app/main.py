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
        if "name_2" not in client_columns:
            connection.execute(text("ALTER TABLE clients ADD COLUMN name_2 VARCHAR(512)"))
        if "conversion_multiplier" not in product_columns:
            connection.execute(
                text("ALTER TABLE products ADD COLUMN conversion_multiplier NUMERIC(14, 3) NOT NULL DEFAULT 1")
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
)

app.include_router(api_router)
