from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class Product(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_code: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(512), index=True, nullable=False)
    price_code: Mapped[str | None] = mapped_column(String(128))
    exchange_code: Mapped[str | None] = mapped_column(String(128), index=True)
    article: Mapped[str | None] = mapped_column(String(128), index=True)
    stock: Mapped[str | None] = mapped_column(String(128))
    trade_mark: Mapped[str | None] = mapped_column(String(256), index=True)
    trade_mark_id: Mapped[int | None] = mapped_column(ForeignKey("product_trade_marks.id"), index=True)
    brand: Mapped[str | None] = mapped_column(String(256), index=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("product_brands.id"), index=True)
    product_type: Mapped[str | None] = mapped_column(String(128), index=True)
    product_type_id: Mapped[int | None] = mapped_column(ForeignKey("product_types.id"), index=True)
    conversion_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("1"), nullable=False
    )
    exclude_from_export: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    barcodes: Mapped[list["ProductBarcode"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    brand_ref = relationship("ProductBrand")
    trade_mark_ref = relationship("ProductTradeMark")
    product_type_ref = relationship("ProductTypeCatalog")


class ProductBrand(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "product_brands"
    __table_args__ = (UniqueConstraint("normalized_name", name="uq_product_brands_normalized_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProductTradeMark(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "product_trade_marks"
    __table_args__ = (UniqueConstraint("normalized_name", name="uq_product_trade_marks_normalized_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProductTypeCatalog(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "product_types"
    __table_args__ = (UniqueConstraint("normalized_name", name="uq_product_types_normalized_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    warehouse_no: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProductBarcode(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "product_barcodes"
    __table_args__ = (
        UniqueConstraint("product_id", "barcode", name="uq_product_barcodes_product_barcode"),
        Index("ix_product_barcodes_barcode_active", "barcode", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True, nullable=False)
    barcode: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    barcode_type: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str | None] = mapped_column(String(128))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    product: Mapped[Product] = relationship(back_populates="barcodes")


class ProductTypeExportRule(Base, TimestampMixin):
    __tablename__ = "product_type_export_rules"
    __table_args__ = (UniqueConstraint("product_type", name="uq_product_type_export_rules_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_type: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    exclude_from_export: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
