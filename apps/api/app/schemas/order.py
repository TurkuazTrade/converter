from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_number: str | None
    converter_type: str | None
    converter_version: str | None
    client_id: int | None
    source_file_id: int | None
    export_file_id: int | None
    export_downloaded_at: datetime | None
    export_downloads: dict | None
    status: str
    error_message: str | None
    source_hash: str | None
    created_at: datetime
    updated_at: datetime


class OrderDetail(OrderRead):
    parsed_snapshot: dict | None
    duplicate_of_order_id: int | None


class UploadOrderResponse(BaseModel):
    order: OrderRead | None = None
    duplicate: bool = False
    existing_order_id: int | None = None
    message: str
