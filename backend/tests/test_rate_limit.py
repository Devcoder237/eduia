"""Limitation de débit, quotas quotidiens et gestion des erreurs du fournisseur IA."""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from conftest import PASSWORD
from httpx import AsyncClient

from app.core.config import settings
from app.core.rate_limit import SlidingWindowLimiter


def test_sliding_window_blocks_then_recovers(monkeypatch: Any) -> None:
    clock = {"t": 1000.0}
    monkeypatch.setattr("app.core.rate_limit.time", SimpleNamespace(monotonic=lambda: clock["t"]))
    limiter = SlidingWindowLimiter()
    assert [limiter.check("k", 3, 60) for _ in range(3)] == [None, None, None]
    retry = limiter.check("k", 3, 60)
    assert retry is not None and 1 <= retry <= 61
    assert limiter.check("other", 3, 60) is None  # clés indépendantes
    clock["t"] += 61
    assert limiter.check("k", 3, 60) is None


def test_limiter_memory_is_bounded(monkeypatch: Any) -> None:
    monkeypatch.setattr("app.core.rate_limit._MAX_KEYS", 50)
    clock = {"t": 0.0}
    monkeypatch.setattr("app.core.rate_limit.time", SimpleNamespace(monotonic=lambda: clock["t"]))
    limiter = SlidingWindowLimiter()
    for i in range(200):
        clock["t"] += 1
        limiter.check(f"k{i}", 5, 10)
    assert len(limiter._hits) <= 60


async def test_login_brute_force_is_throttled(
    client: AsyncClient, signup: Callable[..., Any], limits_on: None, monkeypatch: Any
) -> None:
    monkeypatch.setattr(settings, "RL_AUTH_PER_MIN", 3)
    await signup("alice")
    statuses = []
    for _ in range(5):
        r = await client.post("/api/auth/login", json={"email": "alice@example.com", "password": "Wrong123"})
        statuses.append(r.status_code)
    assert statuses[:3] == [401, 401, 401] or 429 in statuses
    assert 429 in statuses
    blocked = await client.post("/api/auth/login", json={"email": "alice@example.com", "password": PASSWORD})
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) >= 1


async def test_register_is_throttled_per_ip(client: AsyncClient, limits_on: None, monkeypatch: Any) -> None:
    monkeypatch.setattr(settings, "RL_REGISTER_PER_HOUR", 2)
    codes = []
    for i in range(4):
        r = await client.post(
            "/api/auth/register",
            json={"email": f"u{i}@example.com", "username": f"user{i}", "password": PASSWORD},
        )
        codes.append(r.status_code)
    assert codes[:2] == [201, 201] and codes[2:] == [429, 429]


async def test_daily_llm_quota_blocks_with_friendly_message(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any, monkeypatch: Any
) -> None:
    monkeypatch.setattr(settings, "DAILY_LLM_QUOTA", 2)
    acct = await signup()
    body = {"subject": "mathematiques", "level": "college", "topic": "Somme"}
    assert (await client.post("/api/exercises/generate", headers=acct.headers, json=body)).status_code == 200
    assert (await client.post("/api/exercises/generate", headers=acct.headers, json=body)).status_code == 200
    blocked = await client.post("/api/exercises/generate", headers=acct.headers, json=body)
    assert blocked.status_code == 429
    assert "demain" in blocked.json()["detail"]
    assert fake_llm.json_calls == 2  # aucun appel payant au-delà du quota

    other = await signup("bob")  # le quota est par utilisateur
    assert (await client.post("/api/exercises/generate", headers=other.headers, json=body)).status_code == 200


async def test_per_minute_llm_limit(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any, limits_on: None, monkeypatch: Any
) -> None:
    monkeypatch.setattr(settings, "RL_LLM_PER_MIN", 2)
    acct = await signup()
    body = {"subject": "mathematiques", "level": "college", "topic": "Somme"}
    codes = [
        (await client.post("/api/exercises/generate", headers=acct.headers, json=body)).status_code
        for _ in range(3)
    ]
    assert codes == [200, 200, 429]


async def test_provider_failure_returns_friendly_error_and_hides_details(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    fake_llm.fail = True
    acct = await signup()
    r = await client.post(
        "/api/exercises/generate",
        headers=acct.headers,
        json={"subject": "mathematiques", "level": "college", "topic": "x"},
    )
    assert r.status_code == 502
    assert "sk-" not in r.text and "Traceback" not in r.text


async def test_health_does_not_touch_database_and_has_security_headers(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "healthy"}
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-request-id"]
    assert (await client.get("/health/ready")).status_code == 200
