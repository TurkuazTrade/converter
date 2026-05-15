from __future__ import annotations

from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class Client(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("client_code", name="uq_clients_client_code"),
        Index("ix_clients_network_address", "network_name", "normalized_address"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    client_code: Mapped[str | None] = mapped_column(String(128), index=True)
    client_code_2: Mapped[str | None] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    name_2: Mapped[str | None] = mapped_column(String(512), index=True)
    normalized_name: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    address: Mapped[str | None] = mapped_column(String(1024))
    normalized_address: Mapped[str | None] = mapped_column(String(1024), index=True)
    network_name: Mapped[str | None] = mapped_column(String(128), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
