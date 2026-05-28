from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_login_delegates_to_identity_service(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(settings, "identity_api_url", "http://identity:8020/api/v1")

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
            "url": "http://identity:8020/api/v1/auth/login",
            "json": {"email": settings.default_test_user_email, "password": "password"},
            "timeout": 10.0,
        }
    ]


def test_login_returns_503_when_identity_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(settings, "identity_api_url", "http://identity:8020/api/v1")

    def fake_post(url: str, *, json: dict[str, str], timeout: float) -> httpx.Response:
        raise httpx.ConnectError("unavailable")

    monkeypatch.setattr(httpx, "post", fake_post)

    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"email": "user", "password": "password"})

    assert response.status_code == 503
    assert response.json()["detail"] == "Identity service is unavailable"
