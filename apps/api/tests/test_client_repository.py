from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.client import Client
from app.repositories.clients import ClientRepository
from app.utils.normalization import normalize_key


def test_client_repository_search_ignores_case_for_cyrillic_name(db_session: Session) -> None:
    db_session.add_all(
        [
            Client(
                client_code="C-1",
                name="ГЛОБУС Бишкек",
                normalized_name=normalize_key("ГЛОБУС Бишкек"),
                is_active=True,
            ),
            Client(
                client_code="C-2",
                name="Народный",
                normalized_name=normalize_key("Народный"),
                is_active=True,
            ),
        ]
    )
    db_session.flush()

    clients = ClientRepository(db_session).list(search="глобус")

    assert [client.client_code for client in clients] == ["C-1"]
