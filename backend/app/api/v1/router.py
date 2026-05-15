from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, clients, files, health, orders, products, references

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
api_router.include_router(references.router, prefix="/references", tags=["references"])
api_router.include_router(orders.router, prefix="/orders", tags=["orders"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
