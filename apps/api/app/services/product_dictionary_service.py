from __future__ import annotations

from typing import TypeAlias

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.product import Product, ProductBrand, ProductTradeMark, ProductTypeCatalog
from app.utils.normalization import normalize_key, normalize_product_type, normalize_text

DictionaryModel: TypeAlias = type[ProductBrand] | type[ProductTradeMark] | type[ProductTypeCatalog]


class ProductDictionaryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def sync_product(self, product: Product) -> None:
        brand = self.get_or_create(ProductBrand, product.brand)
        trade_mark = self.get_or_create(ProductTradeMark, product.trade_mark)
        product_type = self.get_or_create(ProductTypeCatalog, product.product_type, normalize_as_type=True)
        product.brand_id = brand.id if brand else None
        product.trade_mark_id = trade_mark.id if trade_mark else None
        product.product_type_id = product_type.id if product_type else None
        product.brand = brand.name if brand else None
        product.trade_mark = trade_mark.name if trade_mark else None
        product.product_type = product_type.name if product_type else None

    def get_or_create(
        self,
        model: DictionaryModel,
        value: object,
        *,
        normalize_as_type: bool = False,
    ):
        name = normalize_product_type(value) if normalize_as_type else normalize_text(value)
        if not name:
            return None
        normalized_name = self._normalized_key(name, normalize_as_type=normalize_as_type)
        item = self.db.scalar(
            select(model).where(
                model.normalized_name == normalized_name,
                model.deleted_at.is_(None),
            )
        )
        if item is not None:
            if not item.name:
                item.name = name
            return item
        item = model(name=name, normalized_name=normalized_name, is_active=True)
        self.db.add(item)
        self.db.flush()
        return item

    def update_dictionary_item(
        self,
        item,
        *,
        name: str | None = None,
        warehouse_no: str | None = None,
        is_active: bool | None = None,
        normalize_as_type: bool = False,
    ):
        if name is not None:
            normalized_name = normalize_product_type(name) if normalize_as_type else normalize_text(name)
            if not normalized_name:
                raise ValueError("Name is required.")
            item.name = normalized_name
            item.normalized_name = self._normalized_key(normalized_name, normalize_as_type=normalize_as_type)
            self._sync_products_for_item(item, normalize_as_type=normalize_as_type)
        if is_active is not None:
            item.is_active = is_active
        if warehouse_no is not None and hasattr(item, "warehouse_no"):
            item.warehouse_no = normalize_text(warehouse_no) or None
        return item

    def _sync_products_for_item(self, item, *, normalize_as_type: bool) -> None:
        if isinstance(item, ProductBrand):
            products = self.db.scalars(select(Product).where(Product.brand_id == item.id))
            for product in products:
                product.brand = item.name
        elif isinstance(item, ProductTradeMark):
            products = self.db.scalars(select(Product).where(Product.trade_mark_id == item.id))
            for product in products:
                product.trade_mark = item.name
        elif isinstance(item, ProductTypeCatalog):
            products = self.db.scalars(select(Product).where(Product.product_type_id == item.id))
            for product in products:
                product.product_type = normalize_product_type(item.name) if normalize_as_type else item.name

    @staticmethod
    def _normalized_key(value: object, *, normalize_as_type: bool = False) -> str:
        if normalize_as_type:
            return normalize_product_type(value) or ""
        return normalize_key(value)
