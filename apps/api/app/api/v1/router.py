from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1 import auth, clients, files, health, orders, products, references
from app.api.v1.deps import require_permission

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(
    products.router,
    prefix="/products",
    tags=["products"],
    dependencies=[Depends(require_permission("converter.products.read"))],
)
api_router.include_router(
    clients.router,
    prefix="/clients",
    tags=["clients"],
    dependencies=[Depends(require_permission("converter.clients.read"))],
)
api_router.include_router(
    references.router,
    prefix="/references",
    tags=["references"],
    dependencies=[Depends(require_permission("converter.references.read"))],
)
api_router.include_router(
    orders.router,
    prefix="/orders",
    tags=["orders"],
    dependencies=[Depends(require_permission("converter.orders.read"))],
)
api_router.include_router(
    files.router,
    prefix="/files",
    tags=["files"],
    dependencies=[Depends(require_permission("converter.files.read"))],
)
