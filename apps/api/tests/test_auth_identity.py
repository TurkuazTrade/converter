from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.api.v1.deps import _branch_claim, _has_permission
from app.core.config import settings
from app.main import app


def test_login_delegates_to_identity_service(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(settings, "identity_api_url", "http://identity:8500/api/v1")

    def fake_post(url: str, *, json: dict[str, str], timeout: float) -> httpx.Response:
        calls.append({"url": url, "json": json, "timeout": timeout})
        return httpx.Response(200, json={"access_token": "identity-token", "token_type": "bearer"})

    monkeypatch.setattr(httpx, "post", fake_post)

    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"email": "user", "password": "password"})

    assert response.status_code == 200
    assert response.json() == {"access_token": "identity-token", "token_type": "bearer"}
    assert calls == [
        {
            "url": "http://identity:8500/api/v1/auth/login",
            "json": {"email": settings.default_test_user_email, "password": "password"},
            "timeout": 10.0,
        }
    ]


def test_login_returns_503_when_identity_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "identity_api_url", "http://identity:8500/api/v1")

    def fake_post(url: str, *, json: dict[str, str], timeout: float) -> httpx.Response:
        raise httpx.ConnectError("unavailable")

    monkeypatch.setattr(httpx, "post", fake_post)

    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"email": "user", "password": "password"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Identity service is unavailable"


def test_branch_claim_accepts_single_numeric_branch_permission_scope() -> None:
    assert _branch_claim({"branch_permissions_by_id": {"7": ["converter.orders.read"]}}) == (
        7,
        None,
        None,
    )


def test_permission_accepts_active_branch_scope() -> None:
    assert _has_permission(
        {
            "active_branch_id": 7,
            "branch_code": "bishkek",
            "branch_permissions_by_id": {"7": ["converter.orders.read"]},
            "branch_permissions": {"bishkek": ["converter.clients.read"]},
            "permissions": [],
        },
        "converter.orders.read",
    )
    assert _has_permission(
        {
            "active_branch_id": 7,
            "branch_code": "bishkek",
            "branch_permissions_by_id": {"7": ["converter.orders.read"]},
            "branch_permissions": {"bishkek": ["converter.clients.read"]},
            "permissions": [],
        },
        "converter.clients.read",
    )


def test_permission_rejects_other_branch_scope() -> None:
    claims = {
        "active_branch_id": 7,
        "branch_code": "bishkek",
        "branch_permissions_by_id": {"8": ["converter.orders.read"]},
        "branch_permissions": {"osh": ["converter.clients.read"]},
        "permissions": [],
    }

    assert not _has_permission(claims, "converter.orders.read")
    assert not _has_permission(claims, "converter.clients.read")
