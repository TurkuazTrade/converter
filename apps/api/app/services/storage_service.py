from __future__ import annotations

import hashlib
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol

from fastapi import UploadFile

from app.core.config import settings
from app.core.enums import FileRole, StorageBackend


@dataclass(slots=True)
class StoredObject:
    original_name: str
    stored_name: str
    path: str
    mime_type: str | None
    size: int
    sha256: str
    file_role: FileRole
    storage_backend: StorageBackend = StorageBackend.LOCAL


class StorageService(Protocol):
    async def save_source(self, upload_file: UploadFile, user_id: int | None = None) -> StoredObject:
        ...

    async def save_quarantine(
        self,
        upload_file: UploadFile,
        reason: str,
        user_id: int | None = None,
    ) -> StoredObject:
        ...

    def get_path(self, storage_path: str) -> Path:
        ...

    def delete(self, storage_path: str) -> None:
        ...


class LocalStorageService:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or settings.storage_root
        settings.ensure_directories()

    async def save_source(self, upload_file: UploadFile, user_id: int | None = None) -> StoredObject:
        return await self._save_upload(upload_file, settings.source_storage_dir, FileRole.SOURCE)

    async def save_quarantine(
        self,
        upload_file: UploadFile,
        reason: str,
        user_id: int | None = None,
    ) -> StoredObject:
        return await self._save_upload(upload_file, settings.quarantine_storage_dir, FileRole.QUARANTINE)

    def get_path(self, storage_path: str) -> Path:
        return Path(storage_path)

    def delete(self, storage_path: str) -> None:
        path = Path(storage_path)
        if path.exists():
            path.unlink()

    async def _save_upload(
        self,
        upload_file: UploadFile,
        target_dir: Path,
        role: FileRole,
    ) -> StoredObject:
        target_dir.mkdir(parents=True, exist_ok=True)
        original_name = upload_file.filename or "upload.bin"
        stored_name = self._stored_name(original_name)
        path = target_dir / stored_name
        digest = hashlib.sha256()
        size = 0
        with path.open("wb") as output:
            while True:
                chunk = await upload_file.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        await upload_file.seek(0)
        return StoredObject(
            original_name=original_name,
            stored_name=stored_name,
            path=str(path),
            mime_type=upload_file.content_type,
            size=size,
            sha256=digest.hexdigest(),
            file_role=role,
        )

    @staticmethod
    def _stored_name(original_name: str) -> str:
        suffix = Path(original_name).suffix
        return f"{uuid.uuid4().hex}{suffix}"
