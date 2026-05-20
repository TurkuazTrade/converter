from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_code: str | None
    name: str
    price_code: str | None
    exchange_code: str | None
    article: str | None
    stock: str | None
    trade_mark: str | None
    trade_mark_id: int | None
    brand: str | None
    brand_id: int | None
    product_type: str | None
    product_type_id: int | None
    conversion_multiplier: float
    exclude_from_export: bool
    is_active: bool
    created_at: datetime
    barcodes: list["ProductBarcodeRead"] = []


class ProductBarcodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    barcode: str
    is_primary: bool
    is_active: bool


class ProductCreate(BaseModel):
    item_code: str | None = None
    name: str
    price_code: str | None = None
    exchange_code: str | None = None
    article: str | None = None
    stock: str | None = None
    trade_mark: str | None = None
    brand: str | None = None
    product_type: str | None = None
    barcode: str | None = None
    conversion_multiplier: float | None = None
    exclude_from_export: bool = False
    is_active: bool = True


class ProductUpdate(BaseModel):
    item_code: str | None = None
    name: str | None = None
    price_code: str | None = None
    exchange_code: str | None = None
    article: str | None = None
    stock: str | None = None
    trade_mark: str | None = None
    brand: str | None = None
    product_type: str | None = None
    barcode: str | None = None
    conversion_multiplier: float | None = None
    exclude_from_export: bool | None = None
    is_active: bool | None = None


class ProductTypeExportRuleRead(BaseModel):
    product_type: str
    exclude_from_export: bool


class ProductTypeExportRuleUpdate(BaseModel):
    product_type: str
    exclude_from_export: bool


class ProductDictionaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    warehouse_no: str | None = None
    is_active: bool
    created_at: datetime


class ProductDictionaryCreate(BaseModel):
    name: str
    warehouse_no: str | None = None
    is_active: bool = True


class ProductDictionaryUpdate(BaseModel):
    name: str | None = None
    warehouse_no: str | None = None
    is_active: bool | None = None
