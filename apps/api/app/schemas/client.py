from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_code: str | None
    name: str
    name_2: str | None
    address: str | None
    network_name: str | None
    is_active: bool
    created_at: datetime


class ClientCreate(BaseModel):
    client_code: str
    name: str
    name_2: str | None = None
    address: str | None = None
    network_name: str | None = None


class ClientUpdate(BaseModel):
    client_code: str | None = None
    name: str | None = None
    name_2: str | None = None
    address: str | None = None
    network_name: str | None = None
    is_active: bool | None = None
