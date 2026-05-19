from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.order import Order


class OrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, limit: int = 100, offset: int = 0) -> list[Order]:
        return list(
            self.db.scalars(
                select(Order).order_by(desc(Order.created_at)).offset(offset).limit(limit)
            )
        )

    def get(self, order_id: int) -> Order | None:
        return self.db.get(Order, order_id)

    def find_by_source_hash(self, source_hash: str) -> Order | None:
        return self.db.scalar(select(Order).where(Order.source_hash == source_hash).order_by(desc(Order.id)))
