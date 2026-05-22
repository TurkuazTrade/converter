from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import OrderItemStatus
from app.models.client import Client
from app.models.mapping import ClientMapping, ProductMapping
from app.models.order import Order, OrderItem
from app.models.product import Product, ProductBarcode
from app.utils.normalization import is_short_numeric_item_code, normalize_key, normalize_text


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
        mapping_conditions = []
        if normalized_name:
            mapping_conditions.append(ClientMapping.normalized_client_name == normalized_name)
        if normalized_address:
            mapping_conditions.append(ClientMapping.normalized_address == normalized_address)
        if mapping_conditions:
            client = self._single_client(
                select(Client)
                .join(ClientMapping, ClientMapping.client_id == Client.id)
                .where(
                    ClientMapping.converter_type == converter_type,
                    ClientMapping.is_active.is_(True),
                    ClientMapping.deleted_at.is_(None),
                    Client.deleted_at.is_(None),
                    Client.is_active.is_(True),
                    or_(*mapping_conditions),
                )
            )
        if client is None and client_code:
            client = self._single_client(
                select(Client).where(
                    Client.client_code == client_code,
                    Client.deleted_at.is_(None),
                    Client.is_active.is_(True),
                )
            )
        if client is None and normalized_name:
            client = self._single_client(
                select(Client).where(
                    Client.normalized_name == normalized_name,
                    Client.deleted_at.is_(None),
                    Client.is_active.is_(True),
                )
            )
        if client is None and normalized_name:
            client = self._single_client_by_name_2(normalized_name)
        if client is not None:
            order.client_id = client.id
        return client

    def _single_client(self, stmt) -> Client | None:
        matches = list(self.db.scalars(stmt.limit(2)))
        return matches[0] if len(matches) == 1 else None

    def _single_client_by_name_2(self, normalized_name: str) -> Client | None:
        matches = [
            client
            for client in self.db.scalars(
                select(Client).where(
                    Client.name_2.is_not(None),
                    Client.deleted_at.is_(None),
                    Client.is_active.is_(True),
                )
            )
            if normalize_key(client.name_2) == normalized_name
        ]
        return matches[0] if len(matches) == 1 else None

    def match_item(self, converter_type: str, item: OrderItem) -> None:
        if item.status == OrderItemStatus.SKIPPED.value:
            return

        if converter_type == "asia_retail" and is_short_numeric_item_code(item.raw_item_code):
            item.product_id = None
            item.item_code = item.raw_item_code or item.normalized_barcode
            item.conversion_multiplier = Decimal("1")
            item.quantity = self._source_quantity(item)
            item.status = OrderItemStatus.SKIPPED.value
            item.error_message = "Skipped because item code is 2-4 digits."
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
            multiplier = self._manual_multiplier(item) or match.conversion_multiplier
            item.product_id = match.product.id
            item.item_code = match.product.item_code or item.raw_item_code or item.normalized_barcode
            self._fill_product_name_from_item(match.product, item)
            item.source_quantity = source_quantity
            item.conversion_multiplier = multiplier
            item.quantity = source_quantity * multiplier
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
        item.source_payload = {**(item.source_payload or {}), "manual_conversion_multiplier": None}
        item.status = OrderItemStatus.SKIPPED.value
        item.error_message = "Skipped by operator."

    @staticmethod
    def _source_quantity(item: OrderItem) -> Decimal:
        return item.source_quantity if item.source_quantity is not None else item.quantity

    @staticmethod
    def _multiplier(value: Decimal | None) -> Decimal:
        return value if value is not None and value > 0 else Decimal("1")

    @staticmethod
    def _manual_multiplier(item: OrderItem) -> Decimal | None:
        payload = item.source_payload or {}
        value = payload.get("manual_conversion_multiplier")
        try:
            multiplier = Decimal(str(value))
        except Exception:
            return None
        return multiplier if multiplier > 0 else None

    def _find_product_match(self, converter_type: str, item: OrderItem) -> ProductMatch | None:
        if item.normalized_barcode:
            mapped = self._single_product_mapping(
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
                    conversion_multiplier=self._product_multiplier(mapped.product),
                )

            by_barcode = self._single_product_by_barcode(item.normalized_barcode)
            if by_barcode is not None:
                return ProductMatch(product=by_barcode, conversion_multiplier=self._product_multiplier(by_barcode))

            by_barcode_as_item_code = self._single_product_by_item_code(item.normalized_barcode)
            if by_barcode_as_item_code is not None:
                return ProductMatch(
                    product=by_barcode_as_item_code,
                    conversion_multiplier=self._product_multiplier(by_barcode_as_item_code),
                )

        if item.raw_item_code:
            mapped_by_item_code = self._single_product_mapping(
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
                    conversion_multiplier=self._product_multiplier(mapped_by_item_code.product),
                )

            by_code = self._single_product_by_item_code(item.raw_item_code)
            if by_code is not None:
                return ProductMatch(product=by_code, conversion_multiplier=self._product_multiplier(by_code))

        if item.normalized_name:
            mapped_by_name = self._single_product_mapping(
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
                    conversion_multiplier=self._product_multiplier(mapped_by_name.product),
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
        self._deactivate_conflicting_product_mappings(
            order.converter_type if order else "",
            product.id,
            item.normalized_barcode,
            normalize_key(item.raw_item_code),
        )
        product.conversion_multiplier = multiplier
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
        self._fill_product_name_from_item(product, item)
        item.product_id = product.id
        item.item_code = product.item_code or item.raw_item_code or item.normalized_barcode
        item.source_quantity = self._source_quantity(item)
        item.conversion_multiplier = multiplier
        item.quantity = item.source_quantity * item.conversion_multiplier
        item.source_payload = {**(item.source_payload or {}), "manual_conversion_multiplier": str(multiplier)}
        item.status = OrderItemStatus.RESOLVED.value
        item.error_message = None

    def _deactivate_conflicting_product_mappings(
        self,
        converter_type: str,
        product_id: int,
        normalized_barcode: str | None,
        normalized_item_code: str | None,
    ) -> None:
        match_conditions = []
        if normalized_barcode:
            match_conditions.append(ProductMapping.normalized_barcode == normalized_barcode)
        if normalized_item_code:
            match_conditions.append(ProductMapping.normalized_item_code == normalized_item_code)
        if not match_conditions:
            return
        for mapping in self.db.scalars(
            select(ProductMapping).where(
                ProductMapping.converter_type == converter_type,
                ProductMapping.product_id != product_id,
                ProductMapping.is_active.is_(True),
                ProductMapping.deleted_at.is_(None),
                or_(*match_conditions),
            )
        ):
            mapping.is_active = False

    def update_item_multiplier(self, order_item_id: int, conversion_multiplier: Decimal | None) -> None:
        item = self.db.get(OrderItem, order_item_id)
        if item is None:
            raise ValueError("Order item not found.")
        multiplier = self._multiplier(conversion_multiplier)
        source_quantity = self._source_quantity(item)
        item.source_quantity = source_quantity
        item.conversion_multiplier = multiplier
        item.quantity = source_quantity * multiplier
        item.source_payload = {**(item.source_payload or {}), "manual_conversion_multiplier": str(multiplier)}
        if item.product is not None:
            item.product.conversion_multiplier = multiplier

    def backfill_product_names_from_orders(self) -> dict[str, int | str]:
        items = list(
            self.db.scalars(
                select(OrderItem)
                .options(selectinload(OrderItem.product))
                .where(
                    OrderItem.product_id.is_not(None),
                    OrderItem.raw_name.is_not(None),
                    OrderItem.status == OrderItemStatus.RESOLVED.value,
                )
                .order_by(OrderItem.id)
            )
        )
        candidates: dict[int, Counter[str]] = defaultdict(Counter)
        products: dict[int, Product] = {}
        for item in items:
            product = item.product
            if product is None or not self._product_name_needs_fill(product):
                continue
            name = self._candidate_product_name(product, item)
            if not name:
                continue
            candidates[product.id][name] += 1
            products[product.id] = product

        updated = 0
        candidate_count = 0
        for product_id, names in candidates.items():
            candidate_count += sum(names.values())
            product = products[product_id]
            if not self._product_name_needs_fill(product):
                continue
            product.name = names.most_common(1)[0][0]
            updated += 1

        return {
            "status": "ok",
            "scanned": len(items),
            "candidates": candidate_count,
            "updated": updated,
        }

    @classmethod
    def _product_multiplier(cls, product: Product) -> Decimal:
        return cls._multiplier(product.conversion_multiplier)

    def _fill_product_name_from_item(self, product: Product, item: OrderItem) -> bool:
        if not self._product_name_needs_fill(product):
            return False
        name = self._candidate_product_name(product, item)
        if not name:
            return False
        product.name = name
        return True

    @staticmethod
    def _product_name_needs_fill(product: Product) -> bool:
        current_name = normalize_text(product.name)
        if not current_name:
            return True
        current_key = normalize_key(current_name)
        technical_keys = {normalize_key(product.item_code)}
        return current_key in technical_keys

    @staticmethod
    def _candidate_product_name(product: Product, item: OrderItem) -> str | None:
        name = normalize_text(item.raw_name)
        if not name:
            return None
        name_key = normalize_key(name)
        technical_keys = {
            normalize_key(product.item_code),
            normalize_key(item.item_code),
            normalize_key(item.raw_item_code),
            normalize_key(item.raw_barcode),
            normalize_key(item.normalized_barcode),
        }
        return None if name_key in technical_keys else name

    @staticmethod
    def _trusted_barcode_condition():
        return or_(ProductBarcode.source.is_(None), ProductBarcode.source != "smoke")

    def _single_product_mapping(self, stmt) -> ProductMapping | None:
        matches = list(self.db.scalars(stmt.limit(2)))
        return matches[0] if len(matches) == 1 else None

    def _single_product_by_barcode(self, barcode: str) -> Product | None:
        matches = list(
            self.db.scalars(
                select(Product)
                .join(ProductBarcode, ProductBarcode.product_id == Product.id)
                .where(
                    ProductBarcode.barcode == barcode,
                    self._trusted_barcode_condition(),
                    ProductBarcode.is_active.is_(True),
                    ProductBarcode.deleted_at.is_(None),
                    Product.deleted_at.is_(None),
                    Product.is_active.is_(True),
                )
                .limit(2)
            )
        )
        return matches[0] if len(matches) == 1 else None

    def _single_product_by_item_code(self, item_code: str) -> Product | None:
        normalized_item_code = normalize_text(item_code).casefold()
        if not normalized_item_code:
            return None

        matches = [
            product
            for product in self.db.scalars(
                select(Product).where(
                    func.lower(Product.item_code) == normalized_item_code,
                    Product.deleted_at.is_(None),
                    Product.is_active.is_(True),
                )
            )
            if normalize_text(product.item_code).casefold() == normalized_item_code
        ]
        if not matches:
            matches = [
                product
                for product in self.db.scalars(
                    select(Product).where(
                        Product.item_code.is_not(None),
                        Product.deleted_at.is_(None),
                        Product.is_active.is_(True),
                    )
                )
                if normalize_text(product.item_code).casefold() == normalized_item_code
            ]
        return matches[0] if len(matches) == 1 else None

    def save_client_mapping(self, order_id: int, client_id: int, user_id: int) -> None:
        order = self.db.get(Order, order_id)
        client = self.db.get(Client, client_id)
        if order is None or client is None:
            raise ValueError("Order or client not found.")
        hint = (order.parsed_snapshot or {}).get("client_hint") or {}
        normalized_client_name = normalize_key(hint.get("raw_name")) or None
        normalized_address = normalize_key(hint.get("raw_address")) or None
        self._deactivate_conflicting_client_mappings(
            order.converter_type or "",
            client.id,
            normalized_client_name,
            normalized_address,
        )
        mapping = ClientMapping(
            converter_type=order.converter_type or "",
            raw_client_name=hint.get("raw_name"),
            normalized_client_name=normalized_client_name,
            raw_address=hint.get("raw_address"),
            normalized_address=normalized_address,
            client_id=client.id,
            created_by_id=user_id,
        )
        self.db.add(mapping)
        order.client_id = client.id

    def _deactivate_conflicting_client_mappings(
        self,
        converter_type: str,
        client_id: int,
        normalized_client_name: str | None,
        normalized_address: str | None,
    ) -> None:
        conditions = []
        if normalized_client_name:
            conditions.append(ClientMapping.normalized_client_name == normalized_client_name)
        if normalized_address:
            conditions.append(ClientMapping.normalized_address == normalized_address)
        if not conditions:
            return
        for mapping in self.db.scalars(
            select(ClientMapping).where(
                ClientMapping.converter_type == converter_type,
                ClientMapping.client_id != client_id,
                ClientMapping.is_active.is_(True),
                ClientMapping.deleted_at.is_(None),
                or_(*conditions),
            )
        ):
            mapping.is_active = False
