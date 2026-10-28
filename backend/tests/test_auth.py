"""Inscription, connexion, refresh, révocation des jetons, suppression de compte."""

from collections.abc import Callable
from typing import Any

from conftest import PASSWORD
from httpx import AsyncClient


async def test_register_returns_user_without_secrets(client: AsyncClient) -> None:
    r = await client.post(
        "/api/auth/register",
        json={"email": "Bob@Example.com", "username": "bob", "password": PASSWORD, "full_name": "Bob"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "bob@example.com"  # normalisé en minuscules
    assert body["is_admin"] is False and body["is_teacher"] is False
    assert "hashed_pwd" not in body and "password" not in body


async def test_register_cannot_grant_roles(client: AsyncClient) -> None:
    r = await client.post(
        "/api/auth/register",
        json={
            "email": "eve@example.com",
            "username": "eve",
            "password": PASSWORD,
            "is_admin": True,
            "is_teacher": True,
        },
    )
    assert r.status_code == 201
    assert r.json()["is_admin"] is False and r.json()["is_teacher"] is False


async def test_register_duplicate_email_and_username(client: AsyncClient, signup: Callable[..., Any]) -> None:
    await signup("alice")
    dup_email = await client.post(
        "/api/auth/register", json={"email": "alice@example.com", "username": "other", "password": PASSWORD}
    )
    dup_user = await client.post(
        "/api/auth/register", json={"email": "other@example.com", "username": "alice", "password": PASSWORD}
    )
    assert dup_email.status_code == 409
    assert dup_user.status_code == 409


async def test_register_rejects_weak_or_too_long_passwords(client: AsyncClient) -> None:
    base = {"email": "w@example.com", "username": "weakling"}
    for bad in ("short1A", "alllowercase1", "NoDigitsHere", "A1" + "é" * 40):
        r = await client.post("/api/auth/register", json={**base, "password": bad})
        assert r.status_code == 422, bad


async def test_login_wrong_password_is_generic(client: AsyncClient, signup: Callable[..., Any]) -> None:
    await signup("alice")
    wrong = await client.post("/api/auth/login", json={"email": "alice@example.com", "password": "Wrong123"})
    unknown = await client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "Wrong123"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]  # pas d'énumération de comptes


async def test_protected_route_requires_token(client: AsyncClient) -> None:
    assert (await client.get("/api/auth/me")).status_code == 401
    bad = await client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert bad.status_code == 401


async def test_refresh_token_flow_and_type_confusion(client: AsyncClient, signup: Callable[..., Any]) -> None:
    account = await signup("alice")
    refreshed = await client.post(
        "/api/auth/refresh", json={"refresh_token": account.tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]

    # Un access token ne peut pas servir de refresh token, et inversement.
    assert (
        await client.post("/api/auth/refresh", json={"refresh_token": account.tokens["access_token"]})
    ).status_code == 401
    as_access = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {account.tokens['refresh_token']}"}
    )
    assert as_access.status_code == 401


async def test_password_change_revokes_old_tokens(client: AsyncClient, signup: Callable[..., Any]) -> None:
    account = await signup("alice")
    r = await client.put(
        "/api/auth/password",
        headers=account.headers,
        json={"current_password": PASSWORD, "new_password": "NewSecret456"},
    )
    assert r.status_code == 200
    assert (await client.get("/api/auth/me", headers=account.headers)).status_code == 401
    assert (
        await client.post("/api/auth/refresh", json={"refresh_token": account.tokens["refresh_token"]})
    ).status_code == 401
    new_headers = {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}
    assert (await client.get("/api/auth/me", headers=new_headers)).status_code == 200
    login = await client.post("/api/auth/login", json={"email": account.email, "password": "NewSecret456"})
    assert login.status_code == 200


async def test_logout_all_revokes_tokens(client: AsyncClient, signup: Callable[..., Any]) -> None:
    account = await signup("alice")
    assert (await client.post("/api/auth/logout-all", headers=account.headers)).status_code == 200
    assert (await client.get("/api/auth/me", headers=account.headers)).status_code == 401


async def test_delete_account_removes_everything(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    account = await signup("alice")
    session = await client.post(
        "/api/chat/session", headers=account.headers, json={"subject": "mathematiques", "level": "college"}
    )
    assert session.status_code == 200
    ex = await client.post(
        "/api/exercises/generate",
        headers=account.headers,
        json={"subject": "mathematiques", "level": "college", "topic": "Fractions"},
    )
    assert ex.status_code == 200

    wrong = await client.request(
        "DELETE", "/api/auth/me", headers=account.headers, json={"password": "Wrong123"}
    )
    assert wrong.status_code == 400
    ok = await client.request("DELETE", "/api/auth/me", headers=account.headers, json={"password": PASSWORD})
    assert ok.status_code == 200

    assert (await client.get("/api/auth/me", headers=account.headers)).status_code == 401
    login = await client.post("/api/auth/login", json={"email": account.email, "password": PASSWORD})
    assert login.status_code == 401
    # Le compte peut être recréé : l'email est libéré.
    again = await signup("alice")
    assert again.tokens["access_token"]
