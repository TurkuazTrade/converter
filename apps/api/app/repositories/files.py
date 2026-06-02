from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.file import File


class FileRepository:
    def __init__(self, db: Session, branch_id: int | None = None) -> None:
        self.db = db
        self.branch_id = branch_id

    def get(self, file_id: int, branch_id: int | None = None) -> File | None:
        file_row = self.db.get(File, file_id)
        branch_scope = self.branch_id if branch_id is None else branch_id
        if file_row is None or branch_scope is None:
            return file_row
        return file_row if file_row.branch_id == branch_scope else None

    def find_source_by_hash(self, sha256: str, branch_id: int | None = None) -> File | None:
        branch_scope = self.branch_id if branch_id is None else branch_id
        stmt = select(File).where(File.sha256 == sha256, File.file_role == "source")
        if branch_scope is not None:
            stmt = stmt.where(File.branch_id == branch_scope)
        return self.db.scalar(stmt)
