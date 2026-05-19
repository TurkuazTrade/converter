from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    original_name: str
    stored_name: str
    storage_backend: str
    path: str
    mime_type: str | None
    size: int
    sha256: str
    file_role: str
