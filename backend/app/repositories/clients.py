from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.utils.normalization import normalize_key


class ClientRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, search: str = "", limit: int = 100) -> list[Client]:
        base = select(Client).where(Client.deleted_at.is_(None), Client.is_active.is_(True))
        if not search:
            return list(self.db.scalars(base.order_by(Client.name).limit(limit)))

        pattern = f"%{search}%"
        stmt = base.where(
            (Client.name.ilike(pattern))
            | (Client.client_code.ilike(pattern))
            | (Client.client_code_2.ilike(pattern))
            | (Client.address.ilike(pattern))
            | (Client.network_name.ilike(pattern))
        ).order_by(Client.name).limit(limit)
        results = list(self.db.scalars(stmt))
        if results:
            return results

        tokens = [normalize_key(token) for token in re.split(r"\W+", search) if len(normalize_key(token)) >= 3]
        if not tokens:
            tokens = _fallback_tokens(search)
        if not tokens:
            return []

        candidates = list(self.db.scalars(base.order_by(Client.name).limit(1000)))
        scored: list[tuple[int, Client]] = []
        for client in candidates:
            haystack = normalize_key(
                " ".join(
                    value or ""
                    for value in (
                        client.client_code,
                        client.client_code_2,
                        client.name,
                        client.address,
                        client.network_name,
                    )
                )
            )
            score = sum(1 for token in tokens if token in haystack)
            if score:
                scored.append((score, client))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        return [client for _, client in scored[:limit]]


def _fallback_tokens(search: str) -> list[str]:
    normalized = normalize_key(search)
    known = [
        "глобус",
        "народный",
        "спар",
        "spar",
        "достор",
        "азия",
        "ритейл",
        "alma",
        "алма",
        "darkstore",
    ]
    return [token for token in known if token in normalized]
