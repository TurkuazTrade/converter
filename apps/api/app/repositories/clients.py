from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.utils.normalization import normalize_key


class ClientRepository:
    def __init__(self, db: Session, branch_id: int | None = None) -> None:
        self.db = db
        self.branch_id = branch_id

    def list(
        self,
        search: str = "",
        limit: int = 100,
        offset: int = 0,
        branch_id: int | None = None,
    ) -> list[Client]:
        base = select(Client).where(Client.deleted_at.is_(None), Client.is_active.is_(True))
        branch_scope = self.branch_id if branch_id is None else branch_id
        if branch_scope is not None:
            base = base.where(Client.branch_id == branch_scope)
        if not search:
            return list(self.db.scalars(base.order_by(Client.name).offset(offset).limit(limit)))

        search_key = normalize_key(search)
        if not search_key:
            return []
        stmt = base.where(
            Client.search_text.contains(search_key, autoescape=True)
        ).order_by(Client.name).offset(offset).limit(limit)
        return list(self.db.scalars(stmt))
