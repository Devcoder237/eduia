"""Signalement des réponses du tuteur."""

from collections.abc import Callable
from typing import Any

from httpx import AsyncClient


async def test_report_is_stored_and_validated(client: AsyncClient, signup: Callable[..., Any]) -> None:
    acct = await signup("reporter")
    ok = await client.post(
        "/api/reports",
        headers=acct.headers,
        json={"reason": "wrong", "excerpt": "2+2=5", "comment": "Erreur de calcul"},
    )
    assert ok.status_code == 201 and ok.json() == {"status": "ok"}

    bad_reason = await client.post(
        "/api/reports", headers=acct.headers, json={"reason": "spam", "excerpt": "x"}
    )
    assert bad_reason.status_code == 422
    too_long = await client.post(
        "/api/reports", headers=acct.headers, json={"reason": "other", "excerpt": "x" * 601}
    )
    assert too_long.status_code == 422


async def test_report_requires_authentication(client: AsyncClient) -> None:
    r = await client.post("/api/reports", json={"reason": "wrong", "excerpt": "x"})
    assert r.status_code in {401, 403}
