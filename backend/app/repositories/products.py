from __future__ import annotations

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.product import Product, ProductBarcode


class ProductRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, search: str = "", limit: int = 100) -> list[Product]:
        stmt = select(Product).where(Product.deleted_at.is_(None)).order_by(Product.name).limit(limit)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                (Product.name.ilike(pattern))
                | (Product.item_code.ilike(pattern))
                | exists().where(
                    ProductBarcode.product_id == Product.id,
                    ProductBarcode.barcode.ilike(pattern),
                    ProductBarcode.deleted_at.is_(None),
                )
            )
        return list(self.db.scalars(stmt))
