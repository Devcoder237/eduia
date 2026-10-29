"""Temps d'activité réel : signaux de présence, sessions, protections et statistiques."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from app.core.timeutil import utcnow
from app.db import database as dbmod
from app.models.models import ActivitySession

BEAT = "/api/activity/heartbeat"
STATS = "/api/progress/detailed-stats"


async def _beat(client: AsyncClient, account: Any, module: str = "tutor", seconds: int = 30) -> int:
    response = await client.post(BEAT, json={"module": module, "seconds": seconds}, headers=account.headers)
    return response.status_code


async def _sessions() -> list[ActivitySession]:
    async with dbmod.AsyncSessionLocal() as session:
        return list((await session.execute(select(ActivitySession))).scalars().all())


async def _age_last_beat(seconds: int) -> None:
    """Recule le dernier signal dans le temps (simule une attente sans dormir)."""
    async with dbmod.AsyncSessionLocal() as session:
        await session.execute(update(ActivitySession).values(last_beat_at=utcnow() - timedelta(seconds=seconds)))
        await session.commit()


async def test_first_heartbeat_opens_a_session_with_its_credit(client: AsyncClient, signup: Callable[..., Any]) -> None:
    alice = await signup("alice")
    assert await _beat(client, alice, "quiz", 30) == 204
    sessions = await _sessions()
    assert len(sessions) == 1
    assert sessions[0].active_sec == 30
    assert sessions[0].module_seconds == {"quiz": 30}


async def test_replayed_heartbeats_cannot_inflate_time(client: AsyncClient, signup: Callable[..., Any]) -> None:
    alice = await signup("alice")
    await _beat(client, alice, "tutor", 30)
    await _beat(client, alice, "tutor", 60)  # envoyé aussitôt : crédit limité au temps écoulé + tolérance
    total = (await _sessions())[0].active_sec
    assert 30 < total <= 40


async def test_credit_follows_elapsed_time_within_a_session(client: AsyncClient, signup: Callable[..., Any]) -> None:
    alice = await signup("alice")
    await _beat(client, alice, "tutor", 30)
    await _age_last_beat(40)
    await _beat(client, alice, "quiz", 30)
    sessions = await _sessions()
    assert len(sessions) == 1
    assert sessions[0].active_sec == 60
    assert sessions[0].module_seconds == {"tutor": 30, "quiz": 30}


async def test_gap_longer_than_ten_minutes_starts_a_new_session(client: AsyncClient, signup: Callable[..., Any]) -> None:
    alice = await signup("alice")
    await _beat(client, alice, "tutor", 60)
    await _age_last_beat(11 * 60)
    await _beat(client, alice, "tutor", 60)
    assert len(await _sessions()) == 2


async def test_detailed_stats_use_real_active_time(client: AsyncClient, signup: Callable[..., Any]) -> None:
    alice = await signup("alice")
    before = (await client.get(STATS, headers=alice.headers)).json()
    assert before["avg_session_min"] == 0 and before["total_time_min"] == 0

    await _beat(client, alice, "tutor", 60)
    await _age_last_beat(11 * 60)
    await _beat(client, alice, "quiz", 60)
    stats = (await client.get(STATS, headers=alice.headers)).json()
    assert stats["avg_session_min"] == 1.0
    assert stats["total_time_min"] == 2


async def test_each_student_only_counts_their_own_time(client: AsyncClient, signup: Callable[..., Any]) -> None:
    alice = await signup("alice")
    bob = await signup("bob")
    await _beat(client, alice, "tutor", 60)
    stats = (await client.get(STATS, headers=bob.headers)).json()
    assert stats["total_time_min"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"module": "tutor", "seconds": 0},
        {"module": "tutor", "seconds": 61},
        {"module": "inconnu", "seconds": 30},
        {"seconds": 30},
    ],
)
async def test_invalid_heartbeats_are_rejected(
    client: AsyncClient, signup: Callable[..., Any], payload: dict[str, Any]
) -> None:
    alice = await signup("alice")
    response = await client.post(BEAT, json=payload, headers=alice.headers)
    assert response.status_code == 422
    assert await _sessions() == []

async def test_deleting_the_account_removes_activity_time(client: AsyncClient, signup: Callable[..., Any]) -> None:
    """RGPD : le temps d'activité est une donnée personnelle, supprimée avec le compte."""
    alice = await signup("alice")
    await _beat(client, alice, "tutor", 30)
    assert len(await _sessions()) == 1
    response = await client.request("DELETE", "/api/auth/me", headers=alice.headers, json={"password": "Secret123"})
    assert response.status_code == 200, response.text
    assert await _sessions() == []

async def test_heartbeat_requires_authentication(client: AsyncClient) -> None:
    response = await client.post(BEAT, json={"module": "tutor", "seconds": 30})
    assert response.status_code in (401, 403)