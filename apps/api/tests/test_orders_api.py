from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.v1.orders import list_orders
from app.core.enums import OrderStatus
from app.models.order import Order
from app.models.user import User
from app.services.matching_service import MatchingService


def test_list_orders_does_not_rematch_history(
    db_session: Session,
    monkeypatch,
) -> None:
    order = Order(
        order_number="ORD-1",
        converter_type="piton",
        status=OrderStatus.NEEDS_REVIEW.value,
        error_message="Stored review state.",
    )
    db_session.add(order)
    db_session.flush()

    def fail_match_order(self, order_id: int) -> None:
        raise AssertionError("history list should not rematch orders")

    monkeypatch.setattr(MatchingService, "match_order", fail_match_order)

    result = list_orders(
        db=db_session,
        current_user=User(id=1, email="user@example.com", hashed_password="hash"),
        limit=50,
        offset=0,
    )

    assert [item.id for item in result] == [order.id]
    assert result[0].status == OrderStatus.NEEDS_REVIEW.value
    assert result[0].error_message == "Stored review state."
