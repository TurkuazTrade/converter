from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_code: str | None
    name: str
    price_code: str | None
    conversion_multiplier: float
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
    barcode: str | None = None
    conversion_multiplier: float | None = None
    is_active: bool = True


class ProductUpdate(BaseModel):
    item_code: str | None = None
    name: str | None = None
    price_code: str | None = None
    barcode: str | None = None
    conversion_multiplier: float | None = None
    is_active: bool | None = None
