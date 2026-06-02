from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.order import Order


class OrderRepository:
    def __init__(self, db: Session, branch_id: int | None = None) -> None:
        self.db = db
        self.branch_id = branch_id

    def list(self, limit: int = 100, offset: int = 0, branch_id: int | None = None) -> list[Order]:
        branch_scope = self.branch_id if branch_id is None else branch_id
        stmt = select(Order)
        if branch_scope is not None:
            stmt = stmt.where(Order.branch_id == branch_scope)
        stmt = stmt.order_by(desc(Order.created_at)).offset(offset).limit(limit)
        return list(
            self.db.scalars(stmt)
        )

    def get(self, order_id: int, branch_id: int | None = None) -> Order | None:
        order = self.db.get(Order, order_id)
        branch_scope = self.branch_id if branch_id is None else branch_id
        if order is None or branch_scope is None:
            return order
        return order if order.branch_id == branch_scope else None

    def find_by_source_hash(self, source_hash: str, branch_id: int | None = None) -> Order | None:
        branch_scope = self.branch_id if branch_id is None else branch_id
        stmt = select(Order).where(Order.source_hash == source_hash)
        if branch_scope is not None:
            stmt = stmt.where(Order.branch_id == branch_scope)
        stmt = stmt.order_by(desc(Order.id))
        return self.db.scalar(stmt)
