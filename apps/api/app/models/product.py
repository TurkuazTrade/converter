from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin
from app.utils.normalization import build_product_search_text


class Product(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("branch_id", "item_code", name="uq_products_branch_item_code"),
        Index("ix_products_branch_name", "branch_id", "name"),
        Index("ix_products_branch_deleted_name", "branch_id", "deleted_at", "name"),
        Index("ix_products_branch_search", "branch_id", "search_text"),
        Index("ix_products_branch_brand", "branch_id", "brand"),
        Index("ix_products_branch_trade_mark", "branch_id", "trade_mark"),
        Index("ix_products_branch_product_type", "branch_id", "product_type"),
        Index("ix_products_branch_created_at", "branch_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), index=True)
    item_code: Mapped[str | None] = mapped_column(String(128), index=True)
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
    search_text: Mapped[str] = mapped_column(String(2048), default="", nullable=False, index=True)
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
    branch = relationship("Branch")


class ProductBrand(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "product_brands"
    __table_args__ = (
        UniqueConstraint("branch_id", "normalized_name", name="uq_product_brands_branch_normalized_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    branch = relationship("Branch")


class ProductTradeMark(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "product_trade_marks"
    __table_args__ = (
        UniqueConstraint("branch_id", "normalized_name", name="uq_product_trade_marks_branch_normalized_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    branch = relationship("Branch")


class ProductTypeCatalog(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "product_types"
    __table_args__ = (
        UniqueConstraint("branch_id", "normalized_name", name="uq_product_types_branch_normalized_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    warehouse_no: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    branch = relationship("Branch")


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
    __table_args__ = (UniqueConstraint("branch_id", "product_type", name="uq_product_type_export_rules_branch_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), index=True)
    product_type: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    exclude_from_export: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    branch = relationship("Branch")


@event.listens_for(Product, "before_insert")
@event.listens_for(Product, "before_update")
def _sync_product_search_text(mapper, connection, target: Product) -> None:
    target.search_text = build_product_search_text(target)
