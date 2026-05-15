from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
