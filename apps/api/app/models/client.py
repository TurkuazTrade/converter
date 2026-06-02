from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin
from app.utils.normalization import build_client_search_text


class Client(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("branch_id", "client_code", name="uq_clients_branch_client_code"),
        Index("ix_clients_network_address", "branch_id", "network_name", "normalized_address"),
        Index("ix_clients_branch_name", "branch_id", "name"),
        Index("ix_clients_branch_active_name", "branch_id", "deleted_at", "is_active", "name"),
        Index("ix_clients_branch_search", "branch_id", "search_text"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), index=True)
    client_code: Mapped[str | None] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    name_2: Mapped[str | None] = mapped_column(String(512), index=True)
    normalized_name: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    address: Mapped[str | None] = mapped_column(String(1024))
    normalized_address: Mapped[str | None] = mapped_column(String(1024), index=True)
    network_name: Mapped[str | None] = mapped_column(String(128), index=True)
    search_text: Mapped[str] = mapped_column(String(2048), default="", nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    branch = relationship("Branch")


@event.listens_for(Client, "before_insert")
@event.listens_for(Client, "before_update")
def _sync_client_search_text(mapper, connection, target: Client) -> None:
    target.search_text = build_client_search_text(target)
