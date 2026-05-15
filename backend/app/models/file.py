from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import FileRole, StorageBackend
from app.db.base import Base
from app.db.base import TimestampMixin


class File(Base, TimestampMixin):
    __tablename__ = "files"
    __table_args__ = (
        Index("ix_files_sha256_role", "sha256", "file_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_backend: Mapped[str] = mapped_column(
        String(32), default=StorageBackend.LOCAL.value, nullable=False
    )
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    file_role: Mapped[str] = mapped_column(String(32), default=FileRole.SOURCE.value, nullable=False)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)

    uploaded_by = relationship("User", back_populates="uploaded_files")
