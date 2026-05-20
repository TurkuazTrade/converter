from __future__ import annotations

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.product import Product, ProductBarcode
from app.utils.normalization import normalize_product_type, normalize_text


class ProductRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        search: str = "",
        limit: int = 100,
        offset: int = 0,
        exclude_from_export: bool | None = None,
        is_active: bool | None = None,
        product_type: str = "",
        brand: str = "",
        trade_mark: str = "",
        sort_by: str = "name",
        sort_dir: str = "asc",
    ) -> list[Product]:
        if search:
            stmt = self.filtered_query(
                search="",
                exclude_from_export=exclude_from_export,
                is_active=is_active,
                product_type=product_type,
                brand=brand,
                trade_mark=trade_mark,
                sort_by=sort_by,
                sort_dir=sort_dir,
            )
            products = [
                product
                for product in self.db.scalars(stmt).unique()
                if self._matches_search(product, search)
            ]
            return products[offset : offset + limit]

        stmt = self.filtered_query(
            search=search,
            exclude_from_export=exclude_from_export,
            is_active=is_active,
            product_type=product_type,
            brand=brand,
            trade_mark=trade_mark,
            sort_by=sort_by,
            sort_dir=sort_dir,
        ).offset(offset).limit(limit)
        return list(self.db.scalars(stmt))

    @staticmethod
    def filtered_query(
        search: str = "",
        exclude_from_export: bool | None = None,
        is_active: bool | None = None,
        product_type: str = "",
        brand: str = "",
        trade_mark: str = "",
        sort_by: str = "name",
        sort_dir: str = "asc",
    ):
        sort_columns = {
            "name": Product.name,
            "item_code": Product.item_code,
            "exchange_code": Product.exchange_code,
            "article": Product.article,
            "stock": Product.stock,
            "trade_mark": Product.trade_mark,
            "brand": Product.brand,
            "product_type": Product.product_type,
            "conversion_multiplier": Product.conversion_multiplier,
            "exclude_from_export": Product.exclude_from_export,
            "is_active": Product.is_active,
            "created_at": Product.created_at,
        }
        sort_column = sort_columns.get(sort_by, Product.name)
        sort_expression = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
        stmt = (
            select(Product)
            .options(selectinload(Product.barcodes))
            .where(Product.deleted_at.is_(None))
            .order_by(sort_expression, Product.id.asc())
        )
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                (Product.name.ilike(pattern))
                | (Product.item_code.ilike(pattern))
                | (Product.exchange_code.ilike(pattern))
                | (Product.article.ilike(pattern))
                | (Product.trade_mark.ilike(pattern))
                | (Product.brand.ilike(pattern))
                | (Product.product_type.ilike(pattern))
                | exists().where(
                    ProductBarcode.product_id == Product.id,
                    ProductBarcode.barcode.ilike(pattern),
                    ProductBarcode.deleted_at.is_(None),
                )
            )
        if exclude_from_export is not None:
            stmt = stmt.where(Product.exclude_from_export.is_(exclude_from_export))
        if is_active is not None:
            stmt = stmt.where(Product.is_active.is_(is_active))
        if product_type:
            stmt = stmt.where(func.lower(Product.product_type) == normalize_product_type(product_type))
        if brand:
            stmt = stmt.where(Product.brand == brand)
        if trade_mark:
            stmt = stmt.where(Product.trade_mark == trade_mark)
        return stmt

    @staticmethod
    def _matches_search(product: Product, search: str) -> bool:
        needle = normalize_text(search).casefold()
        if not needle:
            return True

        values = (
            product.name,
            product.item_code,
            product.exchange_code,
            product.article,
            product.trade_mark,
            product.brand,
            product.product_type,
        )
        if any(needle in normalize_text(value).casefold() for value in values):
            return True
        return any(
            barcode.deleted_at is None and needle in normalize_text(barcode.barcode).casefold()
            for barcode in product.barcodes
        )
