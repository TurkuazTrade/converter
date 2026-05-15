from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.enums import OrderItemStatus, OrderStatus
from app.models.client import Client
from app.models.mapping import ProductMapping
from app.models.order import Order, OrderItem
from app.models.product import Product, ProductBarcode
from app.models.user import User
from app.services.matching_service import MatchingService
from app.services.reprocess_service import ReprocessService


def test_matching_resolves_product_by_barcode(db_session: Session) -> None:
    product = _product(db_session, item_code="ERP-1", barcode="1234567890123")
    order, item = _order_with_item(db_session, barcode="1234567890123")

    MatchingService(db_session).match_order(order.id)

    assert item.product_id == product.id
    assert item.item_code == "ERP-1"
    assert item.status == OrderItemStatus.RESOLVED.value


def test_matching_ignores_smoke_barcode_and_uses_item_code(db_session: Session) -> None:
    smoke_product = _product(db_session, item_code="TEST-PRODUCT-001", name="Test product")
    db_session.add(
        ProductBarcode(
            product_id=smoke_product.id,
            barcode="8690529502011",
            source="smoke",
            is_primary=True,
            is_active=True,
        )
    )
    real_product = _product(db_session, item_code="203150105380107012200040", name="")
    order, item = _order_with_item(db_session, barcode="8690529502011", raw_name="Real source name")
    item.raw_item_code = real_product.item_code
    db_session.flush()

    MatchingService(db_session).match_order(order.id)

    assert item.product_id == real_product.id
    assert item.item_code == "203150105380107012200040"
    assert item.status == OrderItemStatus.RESOLVED.value
    assert real_product.name == "Real source name"


def test_asia_retail_short_numeric_item_code_is_skipped_on_rematch(db_session: Session) -> None:
    product = _product(db_session, item_code="ERP-SHOULD-NOT-MATCH", barcode="4607176441079")
    order, item = _order_with_item(db_session, barcode="4607176441079", raw_name="Short code row")
    order.converter_type = "asia_retail"
    item.raw_item_code = "201"
    db_session.flush()

    MatchingService(db_session).match_order(order.id)

    assert item.product_id is None
    assert item.item_code == "201"
    assert item.status == OrderItemStatus.SKIPPED.value
    assert product.id is not None


def test_matching_resolves_product_by_saved_mapping(db_session: Session) -> None:
    product = _product(db_session, item_code="ERP-2")
    order, item = _order_with_item(db_session, barcode="9999999999999")
    db_session.add(
        ProductMapping(
            converter_type="piton",
            raw_barcode="9999999999999",
            normalized_barcode="9999999999999",
            product_id=product.id,
            is_active=True,
        )
    )
    db_session.flush()

    MatchingService(db_session).match_order(order.id)

    assert item.product_id == product.id
    assert item.item_code == "ERP-2"
    assert item.status == OrderItemStatus.RESOLVED.value


def test_matching_applies_product_conversion_multiplier_once(db_session: Session) -> None:
    product = _product(db_session, item_code="ERP-BOX", conversion_multiplier=Decimal("12"))
    order, item = _order_with_item(db_session, barcode="9999999999999")
    item.quantity = Decimal("3")
    item.source_quantity = Decimal("3")
    db_session.add(
        ProductMapping(
            converter_type="piton",
            raw_barcode="9999999999999",
            normalized_barcode="9999999999999",
            conversion_multiplier=Decimal("12"),
            product_id=product.id,
            is_active=True,
        )
    )
    db_session.flush()

    service = MatchingService(db_session)
    service.match_order(order.id)
    service.match_order(order.id)

    assert item.product_id == product.id
    assert item.item_code == "ERP-BOX"
    assert item.source_quantity == Decimal("3.000")
    assert item.conversion_multiplier == Decimal("12.000")
    assert item.quantity == Decimal("36.000")
    assert item.status == OrderItemStatus.RESOLVED.value


def test_matching_keeps_unknown_barcode_unresolved(db_session: Session) -> None:
    order, item = _order_with_item(db_session, barcode="404")

    MatchingService(db_session).match_order(order.id)

    assert item.product_id is None
    assert item.status == OrderItemStatus.UNRESOLVED.value
    assert "Product not found" in (item.error_message or "")


def test_skip_item_survives_rematch(db_session: Session) -> None:
    order, item = _order_with_item(db_session, barcode="404")

    service = MatchingService(db_session)
    service.skip_item(item.id)
    service.match_order(order.id)

    assert item.product_id is None
    assert item.status == OrderItemStatus.SKIPPED.value
    assert item.error_message == "Skipped by operator."


def test_matching_does_not_auto_assign_by_similar_name(db_session: Session) -> None:
    _product(db_session, item_code="ERP-3", name="Very Similar Product")
    order, item = _order_with_item(db_session, barcode=None, raw_name="Very Similar Product")

    MatchingService(db_session).match_order(order.id)

    assert item.product_id is None
    assert item.status == OrderItemStatus.UNRESOLVED.value


def test_matching_fills_empty_product_name_from_order_item(db_session: Session) -> None:
    product = _product(db_session, item_code="ERP-NAME", name="", barcode="123")
    order, item = _order_with_item(db_session, barcode="123", raw_name="Order Product Name")

    MatchingService(db_session).match_order(order.id)

    assert item.product_id == product.id
    assert product.name == "Order Product Name"


def test_matching_does_not_overwrite_existing_product_name(db_session: Session) -> None:
    product = _product(db_session, item_code="ERP-NAMED", name="Catalog Product", barcode="321")
    order, item = _order_with_item(db_session, barcode="321", raw_name="Network Product")

    MatchingService(db_session).match_order(order.id)

    assert item.product_id == product.id
    assert product.name == "Catalog Product"


def test_matching_resolves_client_by_second_name(db_session: Session) -> None:
    client = Client(
        client_code="120-04-1-03-8812",
        name="Азия Ритейл-12",
        name_2="Гипермаркет 12",
        normalized_name="азияритейл12",
        is_active=True,
    )
    order = Order(
        converter_type="asia_retail",
        status=OrderStatus.PROCESSING.value,
        parsed_snapshot={"client_hint": {"raw_name": "Гипермаркет 12"}},
    )
    db_session.add_all([client, order])
    db_session.flush()

    MatchingService(db_session).match_client(order)

    assert order.client_id == client.id


def test_matching_resolves_client_by_file_client_code_2(db_session: Session) -> None:
    client = Client(
        client_code="PANORAMA-001",
        client_code_2="120-04-1-03-8812",
        name="Азия Ритейл-12",
        normalized_name="азияритейл12",
        is_active=True,
    )
    order = Order(
        converter_type="asia_retail",
        status=OrderStatus.PROCESSING.value,
        parsed_snapshot={"client_hint": {"raw_name": "Гипермаркет 12", "client_code": "120-04-1-03-8812"}},
    )
    db_session.add_all([client, order])
    db_session.flush()

    MatchingService(db_session).match_client(order)

    assert order.client_id == client.id


def test_matching_leaves_client_unresolved_when_name_matches_multiple_clients(
    db_session: Session,
) -> None:
    first = Client(
        client_code="CLIENT-1",
        name="Азия Ритейл-1",
        name_2="Гипермаркет",
        normalized_name="азияритейл1",
        is_active=True,
    )
    second = Client(
        client_code="CLIENT-2",
        name="Азия Ритейл-2",
        name_2="Гипермаркет",
        normalized_name="азияритейл2",
        is_active=True,
    )
    order = Order(
        converter_type="asia_retail",
        status=OrderStatus.PROCESSING.value,
        parsed_snapshot={"client_hint": {"raw_name": "Гипермаркет"}},
    )
    db_session.add_all([first, second, order])
    db_session.flush()

    MatchingService(db_session).match_client(order)

    assert order.client_id is None


def test_backfill_product_names_from_order_items(db_session: Session) -> None:
    product = _product(db_session, item_code="ERP-BACKFILL", name="")
    order, item = _order_with_item(db_session, barcode="555", raw_name="Rare Network Name")
    item.product_id = product.id
    item.status = OrderItemStatus.RESOLVED.value
    order_2, item_2 = _order_with_item(db_session, barcode="556", raw_name="Popular Network Name")
    item_2.product_id = product.id
    item_2.status = OrderItemStatus.RESOLVED.value
    order_3, item_3 = _order_with_item(db_session, barcode="557", raw_name="Popular Network Name")
    item_3.product_id = product.id
    item_3.status = OrderItemStatus.RESOLVED.value
    db_session.flush()

    result = MatchingService(db_session).backfill_product_names_from_orders()

    assert result["scanned"] == 3
    assert result["updated"] == 1
    assert product.name == "Popular Network Name"


def test_resolve_mapping_then_rematch_sets_order_ready(db_session: Session) -> None:
    product = _product(db_session, item_code="ERP-4")
    client = Client(
        client_code="100245",
        name="Client",
        normalized_name="client",
        is_active=True,
    )
    db_session.add(client)
    user = User(
        email="operator@example.com",
        hashed_password="hash",
        full_name="Operator",
        role="operator",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    order, item = _order_with_item(db_session, barcode="777", client_id=client.id)
    order.status = OrderStatus.NEEDS_REVIEW.value
    db_session.flush()

    MatchingService(db_session).save_product_mapping(item.id, product.id, user_id=user.id)
    result = ReprocessService(db_session).rematch_only(order.id, user_id=user.id)

    assert result["status"] == OrderStatus.READY_TO_EXPORT.value
    assert order.status == OrderStatus.READY_TO_EXPORT.value
    assert item.product_id == product.id
    assert item.status == OrderItemStatus.RESOLVED.value


def test_manual_resolve_can_save_conversion_multiplier(db_session: Session) -> None:
    product = _product(db_session, item_code="ERP-MANUAL")
    user = User(
        email="manual@example.com",
        hashed_password="hash",
        full_name="Manual",
        role="operator",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    order, item = _order_with_item(db_session, barcode="manual-barcode")
    item.quantity = Decimal("5")
    item.source_quantity = Decimal("5")
    db_session.flush()

    MatchingService(db_session).save_product_mapping(
        item.id,
        product.id,
        user_id=user.id,
        conversion_multiplier=Decimal("0.5"),
    )
    result = ReprocessService(db_session).rematch_only(order.id, user_id=user.id)

    assert result["status"] == OrderStatus.NEEDS_REVIEW.value
    assert item.product_id == product.id
    assert item.source_quantity == Decimal("5.000")
    assert item.conversion_multiplier == Decimal("0.500")
    assert item.quantity == Decimal("2.500")


def test_update_multiplier_survives_rematch(db_session: Session) -> None:
    product = _product(db_session, item_code="ERP-MULT", barcode="555")
    order, item = _order_with_item(db_session, barcode="555")
    item.source_quantity = Decimal("4")
    item.quantity = Decimal("4")
    db_session.flush()

    service = MatchingService(db_session)
    service.match_order(order.id)
    service.update_item_multiplier(item.id, Decimal("3"))
    service.match_order(order.id)

    assert item.product_id == product.id
    assert item.status == OrderItemStatus.RESOLVED.value
    assert product.conversion_multiplier == Decimal("3")
    assert item.conversion_multiplier == Decimal("3")
    assert item.quantity == Decimal("12")


def _product(
    db_session: Session,
    *,
    item_code: str,
    name: str = "Product",
    barcode: str | None = None,
    conversion_multiplier: Decimal = Decimal("1"),
) -> Product:
    product = Product(
        item_code=item_code,
        name=name,
        conversion_multiplier=conversion_multiplier,
        is_active=True,
    )
    db_session.add(product)
    db_session.flush()
    if barcode:
        db_session.add(
            ProductBarcode(
                product_id=product.id,
                barcode=barcode,
                is_primary=True,
                is_active=True,
            )
        )
        db_session.flush()
    return product


def _order_with_item(
    db_session: Session,
    *,
    barcode: str | None,
    raw_name: str = "Raw product",
    client_id: int | None = None,
) -> tuple[Order, OrderItem]:
    order = Order(
        converter_type="piton",
        client_id=client_id,
        status=OrderStatus.PROCESSING.value,
        parsed_snapshot={},
    )
    item = OrderItem(
        raw_barcode=barcode,
        normalized_barcode=barcode,
        raw_name=raw_name,
        normalized_name="verysimilarproduct" if raw_name == "Very Similar Product" else None,
        raw_item_code=None,
        quantity=Decimal("1"),
        row_number=6,
        status=OrderItemStatus.UNRESOLVED.value,
    )
    order.items.append(item)
    db_session.add(order)
    db_session.flush()
    return order, item
