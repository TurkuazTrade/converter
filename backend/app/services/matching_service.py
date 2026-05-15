from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import OrderItemStatus
from app.models.client import Client
from app.models.mapping import ClientMapping, ProductMapping
from app.models.order import Order, OrderItem
from app.models.product import Product, ProductBarcode
from app.utils.normalization import normalize_key


@dataclass(frozen=True)
class ProductMatch:
    product: Product
    conversion_multiplier: Decimal


class MatchingService:
    """Reference-backed product/client matching."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def match_order(self, order_id: int) -> None:
        order = self.db.get(Order, order_id)
        if order is None:
            return
        self.match_client(order)
        for item in order.items:
            self.match_item(order.converter_type or "", item)

    def match_client(self, order: Order) -> Client | None:
        snapshot = order.parsed_snapshot or {}
        hint = snapshot.get("client_hint") or {}
        converter_type = order.converter_type or ""
        raw_name = hint.get("raw_name")
        raw_address = hint.get("raw_address")
        client_code = hint.get("client_code")
        normalized_name = normalize_key(raw_name)
        normalized_address = normalize_key(raw_address)

        client = None
        if normalized_name or normalized_address:
            client = self.db.scalar(
                select(Client)
                .join(ClientMapping, ClientMapping.client_id == Client.id)
                .where(
                    ClientMapping.converter_type == converter_type,
                    ClientMapping.is_active.is_(True),
                    ClientMapping.deleted_at.is_(None),
                    Client.deleted_at.is_(None),
                    Client.is_active.is_(True),
                    (
                        (ClientMapping.normalized_client_name == normalized_name)
                        | (ClientMapping.normalized_address == normalized_address)
                    ),
                )
            )
        if client is None and client_code:
            client = self.db.scalar(
                select(Client).where(
                    Client.client_code == client_code,
                    Client.deleted_at.is_(None),
                    Client.is_active.is_(True),
                )
            )
        if client is None and normalized_name:
            client = self.db.scalar(
                select(Client).where(
                    Client.normalized_name == normalized_name,
                    Client.deleted_at.is_(None),
                    Client.is_active.is_(True),
                )
            )
        if client is not None:
            order.client_id = client.id
        return client

    def match_item(self, converter_type: str, item: OrderItem) -> None:
        if item.status == OrderItemStatus.SKIPPED.value:
            return

        source_quantity = self._source_quantity(item)
        item.source_quantity = source_quantity
        item.conversion_multiplier = Decimal("1")
        item.quantity = source_quantity
        if source_quantity <= 0:
            item.status = OrderItemStatus.INVALID_QUANTITY.value
            item.error_message = "Quantity must be greater than zero."
            return

        match = self._find_product_match(converter_type, item)
        if match is not None:
            item.product_id = match.product.id
            item.item_code = match.product.item_code or item.raw_item_code or item.normalized_barcode
            item.source_quantity = source_quantity
            item.conversion_multiplier = match.conversion_multiplier
            item.quantity = source_quantity * match.conversion_multiplier
            item.status = OrderItemStatus.RESOLVED.value
            item.error_message = None
            return

        item.status = OrderItemStatus.UNRESOLVED.value
        item.error_message = (
            f"Product not found by barcode={item.raw_barcode or '-'} "
            f"item_code={item.raw_item_code or '-'}."
        )

    def skip_item(self, order_item_id: int) -> None:
        item = self.db.get(OrderItem, order_item_id)
        if item is None:
            raise ValueError("Order item not found.")
        item.product_id = None
        item.item_code = item.raw_item_code or item.normalized_barcode
        item.conversion_multiplier = Decimal("1")
        item.quantity = self._source_quantity(item)
        item.status = OrderItemStatus.SKIPPED.value
        item.error_message = "Skipped by operator."

    @staticmethod
    def _source_quantity(item: OrderItem) -> Decimal:
        return item.source_quantity if item.source_quantity is not None else item.quantity

    @staticmethod
    def _multiplier(value: Decimal | None) -> Decimal:
        return value if value is not None and value > 0 else Decimal("1")

    def _find_product_match(self, converter_type: str, item: OrderItem) -> ProductMatch | None:
        if item.normalized_barcode:
            mapped = self.db.scalar(
                select(ProductMapping)
                .join(Product, ProductMapping.product_id == Product.id)
                .where(
                    ProductMapping.converter_type == converter_type,
                    ProductMapping.normalized_barcode == item.normalized_barcode,
                    ProductMapping.is_active.is_(True),
                    ProductMapping.deleted_at.is_(None),
                    Product.deleted_at.is_(None),
                    Product.is_active.is_(True),
                )
            )
            if mapped is not None:
                return ProductMatch(
                    product=mapped.product,
                    conversion_multiplier=self._multiplier(mapped.conversion_multiplier),
                )

            by_barcode = self.db.scalar(
                select(Product)
                .join(ProductBarcode, ProductBarcode.product_id == Product.id)
                .where(
                    ProductBarcode.barcode == item.normalized_barcode,
                    ProductBarcode.is_active.is_(True),
                    ProductBarcode.deleted_at.is_(None),
                    Product.deleted_at.is_(None),
                    Product.is_active.is_(True),
                )
            )
            if by_barcode is not None:
                return ProductMatch(product=by_barcode, conversion_multiplier=Decimal("1"))

        if item.raw_item_code:
            mapped_by_item_code = self.db.scalar(
                select(ProductMapping)
                .join(Product, ProductMapping.product_id == Product.id)
                .where(
                    ProductMapping.converter_type == converter_type,
                    ProductMapping.normalized_item_code == normalize_key(item.raw_item_code),
                    ProductMapping.is_active.is_(True),
                    ProductMapping.deleted_at.is_(None),
                    Product.deleted_at.is_(None),
                    Product.is_active.is_(True),
                )
            )
            if mapped_by_item_code is not None:
                return ProductMatch(
                    product=mapped_by_item_code.product,
                    conversion_multiplier=self._multiplier(mapped_by_item_code.conversion_multiplier),
                )

            by_code = self.db.scalar(
                select(Product).where(
                    Product.item_code == item.raw_item_code,
                    Product.deleted_at.is_(None),
                    Product.is_active.is_(True),
                )
            )
            if by_code is not None:
                return ProductMatch(product=by_code, conversion_multiplier=Decimal("1"))

        if item.normalized_name:
            mapped_by_name = self.db.scalar(
                select(ProductMapping)
                .join(Product, ProductMapping.product_id == Product.id)
                .where(
                    ProductMapping.converter_type == converter_type,
                    ProductMapping.normalized_name == item.normalized_name,
                    ProductMapping.is_active.is_(True),
                    ProductMapping.deleted_at.is_(None),
                    Product.deleted_at.is_(None),
                    Product.is_active.is_(True),
                )
            )
            if mapped_by_name is not None:
                return ProductMatch(
                    product=mapped_by_name.product,
                    conversion_multiplier=self._multiplier(mapped_by_name.conversion_multiplier),
                )

        return None

    def save_product_mapping(
        self,
        order_item_id: int,
        product_id: int,
        user_id: int,
        conversion_multiplier: Decimal | None = None,
    ) -> None:
        item = self.db.get(OrderItem, order_item_id)
        product = self.db.get(Product, product_id)
        if item is None or product is None:
            raise ValueError("Order item or product not found.")
        order = self.db.get(Order, item.order_id)
        multiplier = self._multiplier(conversion_multiplier or item.conversion_multiplier)
        mapping = ProductMapping(
            converter_type=order.converter_type if order else "",
            raw_barcode=item.raw_barcode,
            normalized_barcode=item.normalized_barcode,
            raw_item_code=item.raw_item_code,
            normalized_item_code=normalize_key(item.raw_item_code),
            raw_name=item.raw_name,
            normalized_name=item.normalized_name,
            conversion_multiplier=multiplier,
            product_id=product.id,
            created_by_id=user_id,
        )
        self.db.add(mapping)
        self.db.flush()
        item.product_id = product.id
        item.item_code = product.item_code or item.raw_item_code or item.normalized_barcode
        item.source_quantity = self._source_quantity(item)
        item.conversion_multiplier = multiplier
        item.quantity = item.source_quantity * item.conversion_multiplier
        item.status = OrderItemStatus.RESOLVED.value
        item.error_message = None

    def save_client_mapping(self, order_id: int, client_id: int, user_id: int) -> None:
        order = self.db.get(Order, order_id)
        client = self.db.get(Client, client_id)
        if order is None or client is None:
            raise ValueError("Order or client not found.")
        hint = (order.parsed_snapshot or {}).get("client_hint") or {}
        mapping = ClientMapping(
            converter_type=order.converter_type or "",
            raw_client_name=hint.get("raw_name"),
            normalized_client_name=normalize_key(hint.get("raw_name")),
            raw_address=hint.get("raw_address"),
            normalized_address=normalize_key(hint.get("raw_address")),
            client_id=client.id,
            created_by_id=user_id,
        )
        self.db.add(mapping)
        order.client_id = client.id
