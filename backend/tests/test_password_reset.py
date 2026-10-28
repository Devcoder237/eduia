"""Mot de passe oublié : lien par e-mail, usage unique, expiration, pas d'énumération de comptes."""

from datetime import timedelta
from typing import Any

import jwt
import pytest
from conftest import PASSWORD, set_flags
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.core.security import TokenType, create_reset_token, create_token
from app.core.timeutil import utcnow
from app.db import database as dbmod
from app.models.models import User
from app.services import email_service

NEW_PASSWORD = "Nouveau456"
SENT_FR = "Si un compte existe avec cet e-mail, un lien de réinitialisation vient d'être envoyé."


class Outbox:
    """Remplace l'envoi réel : conserve (adresse, lien, langue) de chaque e-mail demandé."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to_address: str, link: str, lang: str) -> bool:
        self.sent.append((to_address, link, lang))
        return True

    def last_token(self) -> str:
        return self.sent[-1][1].split("token=", 1)[1]


@pytest.fixture
def outbox(monkeypatch: pytest.MonkeyPatch) -> Outbox:
    box = Outbox()
    # L'endpoint importe la fonction par son nom : on remplace la référence côté ``auth``.
    monkeypatch.setattr("app.api.auth.send_password_reset_email", box.send)
    return box


async def _forgot(client: AsyncClient, email: str, lang: str | None = None) -> Any:
    headers = {"Accept-Language": lang} if lang else {}
    return await client.post("/api/auth/forgot-password", json={"email": email}, headers=headers)


async def test_forgot_sends_link_for_known_account(client: AsyncClient, signup: Any, outbox: Outbox) -> None:
    acct = await signup()
    response = await _forgot(client, acct.email)
    assert response.status_code == 200
    assert response.json()["status"] == SENT_FR
    assert len(outbox.sent) == 1
    to_address, link, lang = outbox.sent[0]
    assert to_address == acct.email and lang == "fr"
    assert link.startswith(f"{settings.FRONTEND_URL.rstrip('/')}/#/reset?token=")


async def test_forgot_answer_is_identical_for_unknown_account(
    client: AsyncClient, signup: Any, outbox: Outbox
) -> None:
    acct = await signup()
    known = await _forgot(client, acct.email)
    unknown = await _forgot(client, "personne@example.com")
    assert unknown.status_code == known.status_code == 200
    assert unknown.json() == known.json()
    assert len(outbox.sent) == 1  # rien n'est envoyé pour un compte inconnu


async def test_forgot_follows_language_header(client: AsyncClient, signup: Any, outbox: Outbox) -> None:
    acct = await signup()
    response = await _forgot(client, acct.email, "en")
    assert "reset link" in response.json()["status"]
    assert outbox.sent[0][2] == "en"


async def test_forgot_skips_disabled_account(client: AsyncClient, signup: Any, outbox: Outbox) -> None:
    acct = await signup()
    await set_flags(acct.email, is_active=False)
    assert (await _forgot(client, acct.email)).status_code == 200
    assert outbox.sent == []


async def test_reset_changes_password_and_revokes_sessions(
    client: AsyncClient, signup: Any, outbox: Outbox
) -> None:
    acct = await signup()
    await _forgot(client, acct.email)
    reset = await client.post(
        "/api/auth/reset-password", json={"token": outbox.last_token(), "new_password": NEW_PASSWORD}
    )
    assert reset.status_code == 200, reset.text
    old_login = await client.post("/api/auth/login", json={"email": acct.email, "password": PASSWORD})
    new_login = await client.post("/api/auth/login", json={"email": acct.email, "password": NEW_PASSWORD})
    assert old_login.status_code == 401
    assert new_login.status_code == 200
    # Les anciens jetons de connexion sont révoqués.
    assert (await client.get("/api/auth/me", headers=acct.headers)).status_code == 401


async def test_reset_link_works_only_once(client: AsyncClient, signup: Any, outbox: Outbox) -> None:
    acct = await signup()
    await _forgot(client, acct.email)
    token = outbox.last_token()
    first = await client.post("/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    second = await client.post("/api/auth/reset-password", json={"token": token, "new_password": "Autre7890"})
    assert first.status_code == 200
    assert second.status_code == 400
    login = await client.post("/api/auth/login", json={"email": acct.email, "password": NEW_PASSWORD})
    assert login.status_code == 200  # le second essai n'a rien changé


async def test_reset_rejects_expired_link(client: AsyncClient, signup: Any) -> None:
    acct = await signup()
    async with dbmod.AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == acct.email))).scalar_one()
        token = create_reset_token(str(user.id), int(user.token_version or 0), user.hashed_pwd)
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    claims["exp"] = utcnow() - timedelta(minutes=1)
    expired = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    response = await client.post(
        "/api/auth/reset-password", json={"token": expired, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 400


async def test_reset_rejects_other_token_types_and_garbage(client: AsyncClient, signup: Any) -> None:
    acct = await signup()
    for bad in (acct.tokens["access_token"], acct.tokens["refresh_token"], "pas-un-jeton-valide"):
        response = await client.post(
            "/api/auth/reset-password", json={"token": bad, "new_password": NEW_PASSWORD}
        )
        assert response.status_code == 400, bad


async def test_reset_token_is_not_accepted_as_access_token(
    client: AsyncClient, signup: Any, outbox: Outbox
) -> None:
    acct = await signup()
    await _forgot(client, acct.email)
    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {outbox.last_token()}"})
    assert response.status_code == 401


async def test_reset_enforces_password_strength(client: AsyncClient, signup: Any, outbox: Outbox) -> None:
    acct = await signup()
    await _forgot(client, acct.email)
    weak = await client.post(
        "/api/auth/reset-password", json={"token": outbox.last_token(), "new_password": "faible"}
    )
    assert weak.status_code == 422
    # Le lien reste utilisable après un mot de passe refusé.
    ok = await client.post(
        "/api/auth/reset-password", json={"token": outbox.last_token(), "new_password": NEW_PASSWORD}
    )
    assert ok.status_code == 200


async def test_reset_error_message_is_translated(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/reset-password",
        json={"token": "x" * 20, "new_password": NEW_PASSWORD},
        headers={"Accept-Language": "en"},
    )
    assert response.status_code == 400
    assert "invalid or has expired" in response.json()["detail"]


async def test_forgot_is_rate_limited(
    client: AsyncClient, signup: Any, outbox: Outbox, limits_on: None
) -> None:
    acct = await signup()
    codes = [(await _forgot(client, acct.email)).status_code for _ in range(settings.RL_RESET_PER_HOUR + 1)]
    assert codes[:-1] == [200] * settings.RL_RESET_PER_HOUR
    assert codes[-1] == 429


def test_email_body_is_bilingual_and_contains_link() -> None:
    link = "https://exemple.test/#/reset?token=abc"
    fr = email_service.build_reset_body(link, "fr")
    en = email_service.build_reset_body(link, "en")
    assert link in fr and link in en
    assert "Bonjour" in fr and "Hello" in en
    assert str(settings.RESET_TOKEN_EXPIRE_MINUTES) in fr


async def test_email_not_configured_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    assert await email_service.send_password_reset_email("a@example.com", "https://x.test", "fr") is False


async def test_smtp_failure_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.invalid")
    monkeypatch.setattr(settings, "SMTP_FROM", "noreply@example.com")

    def boom(_: Any) -> None:
        raise OSError("réseau indisponible")

    monkeypatch.setattr(email_service, "_send_sync", boom)
    assert await email_service.send_password_reset_email("a@example.com", "https://x.test", "fr") is False


def test_access_and_refresh_types_unchanged() -> None:
    assert TokenType.RESET.value == "reset"
    token, _ = create_token("u1", 0, TokenType.ACCESS)
    assert isinstance(token, str)
