from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.file import File


class FileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, file_id: int) -> File | None:
        return self.db.get(File, file_id)

    def find_source_by_hash(self, sha256: str) -> File | None:
        return self.db.scalar(select(File).where(File.sha256 == sha256, File.file_role == "source"))
