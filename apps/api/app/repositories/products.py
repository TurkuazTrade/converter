from __future__ import annotations

from sqlalchemy import exists, false, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.product import Product, ProductBarcode
from app.utils.normalization import normalize_barcode, normalize_key, normalize_product_type, normalize_text


class ProductRepository:
    def __init__(self, db: Session, branch_id: int | None = None) -> None:
        self.db = db
        self.branch_id = branch_id

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
        branch_id: int | None = None,
    ) -> list[Product]:
        branch_scope = self.branch_id if branch_id is None else branch_id
        stmt = self.filtered_query(
            search=search,
            exclude_from_export=exclude_from_export,
            is_active=is_active,
            product_type=product_type,
            brand=brand,
            trade_mark=trade_mark,
            sort_by=sort_by,
            sort_dir=sort_dir,
            branch_id=branch_scope,
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
        branch_id: int | None = None,
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
        if branch_id is not None:
            stmt = stmt.where(Product.branch_id == branch_id)
        if search:
            search_key = normalize_key(search)
            barcode_search = normalize_barcode(search) or normalize_text(search)
            clauses = []
            if search_key:
                clauses.append(Product.search_text.contains(search_key, autoescape=True))
            if barcode_search:
                clauses.append(
                    exists().where(
                        ProductBarcode.product_id == Product.id,
                        ProductBarcode.barcode.contains(barcode_search, autoescape=True),
                        ProductBarcode.deleted_at.is_(None),
                    )
                )
            if clauses:
                stmt = stmt.where(or_(*clauses))
            else:
                stmt = stmt.where(false())
        if exclude_from_export is not None:
            stmt = stmt.where(Product.exclude_from_export.is_(exclude_from_export))
        if is_active is not None:
            stmt = stmt.where(Product.is_active.is_(is_active))
        if product_type:
            stmt = stmt.where(Product.product_type == normalize_product_type(product_type))
        if brand:
            stmt = stmt.where(Product.brand == brand)
        if trade_mark:
            stmt = stmt.where(Product.trade_mark == trade_mark)
        return stmt
