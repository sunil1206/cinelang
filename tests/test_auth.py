"""Auth endpoint tests."""
from unittest.mock import AsyncMock, patch

import pytest


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_me_unauthenticated(client):
    r = client.get("/api/users/me")
    assert r.status_code == 403  # HTTPBearer returns 403 when header missing


def test_me_authenticated(client, auth_headers, test_user):
    r = client.get("/api/users/me", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == test_user.email
    assert data["name"]  == test_user.name


def test_google_signin_invalid_token(client):
    from app.core.exceptions import AuthError
    with patch(
        "app.services.auth_service.verify_google_id_token",
        new_callable=AsyncMock,
        side_effect=AuthError("Google token verification failed"),
    ):
        r = client.post("/api/auth/google", json={"id_token": "fake"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "auth_error"


def test_google_signin_creates_user(client, db_session):
    fake_claims = {
        "sub":     "google-sub-xyz",
        "email":   "new@example.com",
        "name":    "New User",
        "picture": None,
    }
    with patch(
        "app.services.auth_service.verify_google_id_token",
        new_callable=AsyncMock,
        return_value=fake_claims,
    ):
        r = client.post("/api/auth/google", json={"id_token": "valid-token"})

    assert r.status_code == 200
    body = r.json()
    assert "tokens" in body
    assert body["tokens"]["access_token"]
    assert body["tokens"]["refresh_token"]
    assert body["user"]["email"] == "new@example.com"


def test_refresh_token(client, test_user):
    from app.core.security import create_token
    refresh, _ = create_token(test_user.id, "refresh")
    r = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert r.json()["tokens"]["access_token"]


def test_refresh_with_access_token_fails(client, test_user):
    from app.core.security import create_token
    access, _ = create_token(test_user.id, "access")
    r = client.post("/api/auth/refresh", json={"refresh_token": access})
    assert r.status_code == 401
