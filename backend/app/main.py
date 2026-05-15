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
        if users.get_by_email(settings.default_admin_email) is None:
            users.create_admin(
                email=settings.default_admin_email,
                password=settings.default_admin_password,
                full_name=settings.default_admin_full_name,
            )
            db.commit()


def _ensure_development_columns() -> None:
    inspector = inspect(engine)
    if "clients" not in inspector.get_table_names():
        return
    client_columns = {column["name"] for column in inspector.get_columns("clients")}
    with engine.begin() as connection:
        if "name_2" not in client_columns:
            connection.execute(text("ALTER TABLE clients ADD COLUMN name_2 VARCHAR(512)"))


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
