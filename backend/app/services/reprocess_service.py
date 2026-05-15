from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.enums import OrderItemStatus, OrderStatus, ProcessingEventType
from app.models.order import Order, ProcessingEvent
from app.services.matching_service import MatchingService
from app.services.order_processing_service import OrderProcessingService


class ReprocessService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def rematch_only(self, order_id: int, user_id: int | None = None) -> dict:
        order = self.db.get(Order, order_id)
        if order is None:
            raise ValueError("Order not found.")
        MatchingService(self.db).match_order(order_id)
        unresolved_count = sum(
            1
            for item in order.items
            if item.status in {OrderItemStatus.UNRESOLVED.value, OrderItemStatus.INVALID_QUANTITY.value}
        )
        client_unresolved = order.client_id is None
        order.status = (
            OrderStatus.NEEDS_REVIEW.value
            if unresolved_count or client_unresolved
            else OrderStatus.READY_TO_EXPORT.value
        )
        order.error_message = self._review_message(unresolved_count, client_unresolved)
        self.db.add(
            ProcessingEvent(
                order_id=order_id,
                event_type=ProcessingEventType.REPROCESSED.value,
                message="Order rematched from saved snapshot.",
                payload={"unresolved_count": unresolved_count, "client_unresolved": client_unresolved},
                created_by_id=user_id,
            )
        )
        return {"status": order.status, "mode": "rematch_only", "order_id": order_id}

    def full_reparse(self, order_id: int, user_id: int | None = None) -> dict:
        order = OrderProcessingService(self.db).reprocess_order(order_id, user_id=user_id)
        return {"status": order.status, "mode": "full_reparse", "order_id": order_id}

    @staticmethod
    def _review_message(unresolved_count: int, client_unresolved: bool) -> str | None:
        if not unresolved_count and not client_unresolved:
            return None
        parts: list[str] = []
        if client_unresolved:
            parts.append("Client is not resolved.")
        if unresolved_count:
            parts.append(f"{unresolved_count} order item(s) are unresolved or invalid.")
        return " ".join(parts)
