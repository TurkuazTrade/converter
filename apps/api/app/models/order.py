from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import OrderItemStatus, OrderStatus
from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class Order(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_branch_status_created", "branch_id", "status", "created_at"),
        Index("ix_orders_branch_created_at", "branch_id", "created_at"),
        Index("ix_orders_status_created", "status", "created_at"),
        Index("ix_orders_converter_created", "converter_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), index=True)
    order_number: Mapped[str | None] = mapped_column(String(128), index=True)
    converter_type: Mapped[str | None] = mapped_column(String(64), index=True)
    converter_version: Mapped[str | None] = mapped_column(String(32))
    converter_config_hash: Mapped[str | None] = mapped_column(String(64))
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), index=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    source_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"), index=True)
    export_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"), index=True)
    export_downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    export_downloads: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default=OrderStatus.UPLOADED.value, index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    parsed_snapshot: Mapped[dict | None] = mapped_column(JSON)
    source_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    duplicate_of_order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)

    branch = relationship("Branch")
    uploaded_by = relationship("User", back_populates="uploaded_orders")
    client = relationship("Client")
    source_file = relationship("File", foreign_keys=[source_file_id])
    export_file = relationship("File", foreign_keys=[export_file_id])
    duplicate_of = relationship("Order", remote_side=[id])
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    events: Mapped[list["ProcessingEvent"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"
    __table_args__ = (Index("ix_order_items_order_status", "order_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True, nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), index=True)
    raw_barcode: Mapped[str | None] = mapped_column(String(64), index=True)
    normalized_barcode: Mapped[str | None] = mapped_column(String(64), index=True)
    raw_name: Mapped[str | None] = mapped_column(String(512))
    normalized_name: Mapped[str | None] = mapped_column(String(512), index=True)
    raw_item_code: Mapped[str | None] = mapped_column(String(128), index=True)
    item_code: Mapped[str | None] = mapped_column(String(128), index=True)
    source_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    conversion_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("1"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    row_number: Mapped[int | None] = mapped_column()
    status: Mapped[str] = mapped_column(
        String(32), default=OrderItemStatus.UNRESOLVED.value, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    source_payload: Mapped[dict | None] = mapped_column(JSON)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")


class ProcessingEvent(Base, TimestampMixin):
    __tablename__ = "processing_events"
    __table_args__ = (Index("ix_processing_events_order_created", "order_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)

    order = relationship("Order", back_populates="events")
    created_by = relationship("User")
