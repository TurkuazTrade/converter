from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class ProductMapping(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "product_mappings"
    __table_args__ = (
        Index("ix_product_mappings_branch_barcode", "branch_id", "converter_type", "normalized_barcode"),
        Index("ix_product_mappings_branch_item_code", "branch_id", "converter_type", "normalized_item_code"),
        Index("ix_product_mappings_branch_name", "branch_id", "converter_type", "normalized_name"),
        Index("ix_product_mappings_barcode", "converter_type", "normalized_barcode"),
        Index("ix_product_mappings_item_code", "converter_type", "normalized_item_code"),
        Index("ix_product_mappings_name", "converter_type", "normalized_name"),
        UniqueConstraint(
            "converter_type",
            "normalized_barcode",
            "product_id",
            name="uq_product_mappings_converter_barcode_product",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), index=True)
    converter_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    raw_barcode: Mapped[str | None] = mapped_column(String(64), index=True)
    normalized_barcode: Mapped[str | None] = mapped_column(String(64), index=True)
    raw_item_code: Mapped[str | None] = mapped_column(String(128), index=True)
    normalized_item_code: Mapped[str | None] = mapped_column(String(128), index=True)
    raw_name: Mapped[str | None] = mapped_column(String(512))
    normalized_name: Mapped[str | None] = mapped_column(String(512), index=True)
    conversion_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("1"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    branch = relationship("Branch")
    product = relationship("Product")
    created_by = relationship("User")


class ClientMapping(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "client_mappings"
    __table_args__ = (
        Index("ix_client_mappings_branch_name", "branch_id", "converter_type", "normalized_client_name"),
        Index("ix_client_mappings_branch_address", "branch_id", "converter_type", "normalized_address"),
        Index("ix_client_mappings_name", "converter_type", "normalized_client_name"),
        Index("ix_client_mappings_address", "converter_type", "normalized_address"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), index=True)
    converter_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    raw_client_name: Mapped[str | None] = mapped_column(String(512))
    normalized_client_name: Mapped[str | None] = mapped_column(String(512), index=True)
    raw_address: Mapped[str | None] = mapped_column(String(1024))
    normalized_address: Mapped[str | None] = mapped_column(String(1024), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    branch = relationship("Branch")
    client = relationship("Client")
    created_by = relationship("User")
