"""Idempotence : un double clic / un réessai ne double ni les appels IA ni les compteurs."""

from collections.abc import Callable
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.db import database as dbmod
from app.models.models import LearnerProfile, UserBadge

EXERCISE = {"subject": "mathematiques", "level": "college", "topic": "Additions"}


async def _profile(email_user: Any) -> LearnerProfile:
    async with dbmod.AsyncSessionLocal() as s:
        return (await s.execute(select(LearnerProfile))).scalars().first()  # type: ignore[return-value]


async def test_exercise_generation_is_idempotent(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    acct = await signup()
    body = {**EXERCISE, "request_id": "req-12345678"}
    first = await client.post("/api/exercises/generate", headers=acct.headers, json=body)
    second = await client.post("/api/exercises/generate", headers=acct.headers, json=body)
    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert fake_llm.json_calls == 1
    third = await client.post(
        "/api/exercises/generate", headers=acct.headers, json={**EXERCISE, "request_id": "req-87654321"}
    )
    assert third.json()["id"] != first.json()["id"]


async def test_failed_generation_releases_the_key(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    acct = await signup()
    body = {**EXERCISE, "request_id": "req-retry-001"}
    fake_llm.fail = True
    assert (await client.post("/api/exercises/generate", headers=acct.headers, json=body)).status_code == 502
    fake_llm.fail = False
    ok = await client.post("/api/exercises/generate", headers=acct.headers, json=body)
    assert ok.status_code == 200  # le réessai n'est pas bloqué par la clé


async def test_generation_survives_numeric_answer_as_json_number(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    """Régression P0 : `numeric_answer` entier faisait planter la génération."""
    fake_llm.numeric_answer = 4
    acct = await signup()
    r = await client.post("/api/exercises/generate", headers=acct.headers, json=EXERCISE)
    assert r.status_code == 200


async def test_exercise_submit_twice_calls_ai_once_and_updates_profile_once(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    acct = await signup()
    ex = (await client.post("/api/exercises/generate", headers=acct.headers, json=EXERCISE)).json()
    calls_after_generation = fake_llm.json_calls

    payload = {"exercise_id": ex["id"], "answer": "2 + 2 = 4"}
    first = await client.post("/api/exercises/submit", headers=acct.headers, json=payload)
    second = await client.post("/api/exercises/submit", headers=acct.headers, json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["score"] == second.json()["score"] == 1.0
    assert fake_llm.json_calls == calls_after_generation + 1  # une seule correction IA
    assert "Vérification automatique" in first.json()["feedback"]  # contrôle numérique exact

    profile = await _profile(acct)
    assert profile.total_sessions == 1
    async with dbmod.AsyncSessionLocal() as s:
        codes = (await s.execute(select(UserBadge))).scalars().all()
    assert len(codes) == len({b.badge_id for b in codes})  # jamais de badge en double


async def test_quiz_answer_twice_counts_once(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    acct = await signup()
    q = (
        await client.get(
            "/api/quiz/generate",
            headers=acct.headers,
            params={"subject": "mathematiques", "level": "college", "topic": "Somme"},
        )
    ).json()
    assert "correct_index" not in q  # la bonne réponse ne fuit pas vers le client
    body = {"question_id": q["id"], "answer_index": 0, "justification": ""}
    first = await client.post("/api/quiz/answer", headers=acct.headers, json=body)
    second = await client.post("/api/quiz/answer", headers=acct.headers, json=body)
    assert first.status_code == second.status_code == 200
    assert first.json()["correct"] == second.json()["correct"]
    assert first.json()["correct_index"] == second.json()["correct_index"]
    assert (await _profile(acct)).total_questions == 1


async def test_quiz_generate_idempotent_and_unknown_question_404(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    acct = await signup()
    params = {"subject": "physique", "level": "lycee", "topic": "Force", "request_id": "quiz-req-0001"}
    a = (await client.get("/api/quiz/generate", headers=acct.headers, params=params)).json()
    b = (await client.get("/api/quiz/generate", headers=acct.headers, params=params)).json()
    assert a["id"] == b["id"] and fake_llm.json_calls == 1
    legacy = await client.post(
        "/api/quiz/answer", headers=acct.headers, json={"question_id": "x|1|boom", "answer_index": 1}
    )
    assert legacy.status_code == 404  # l'ancien format « id|index|texte » n'est plus accepté


async def test_quiz_session_completion_is_capped_per_day(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any, monkeypatch: Any
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "DAILY_QUIZ_SESSION_CAP", 2)
    acct = await signup()
    for _ in range(5):
        assert (await client.post("/api/quiz/complete-session", headers=acct.headers)).status_code == 200
    assert (await _profile(acct)).total_sessions == 2


async def _start_exam(client: AsyncClient, acct: Any, count: int = 3) -> dict[str, Any]:
    r = await client.post(
        "/api/exams/start",
        headers=acct.headers,
        json={
            "subject": "mathematiques",
            "level": "college",
            "question_count": count,
            "duration_min": 10,
            "request_id": "exam-req-0001",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


async def test_exam_full_flow_is_idempotent(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    acct = await signup()
    start = await _start_exam(client, acct)
    again = await _start_exam(client, acct)
    assert start["exam_id"] == again["exam_id"] and start["first_question"]["index"] == 0
    assert start["expires_at"]  # le chronomètre est côté serveur

    question = start["first_question"]
    for expected_index in (1, 2):
        r = await client.post(
            "/api/exams/answer",
            headers=acct.headers,
            json={"attempt_id": question["attempt_id"], "answer_index": 1},
        )
        assert r.status_code == 200
        assert "correct" not in r.json()  # conditions d'examen : pas de correction en cours de route
        nxt = r.json()["next_question"]
        assert nxt["index"] == expected_index
        # Même réponse rejouée : même question suivante, pas de nouvelle génération.
        calls = fake_llm.json_calls
        replay = await client.post(
            "/api/exams/answer",
            headers=acct.headers,
            json={"attempt_id": question["attempt_id"], "answer_index": 0},
        )
        assert replay.json()["next_question"]["attempt_id"] == nxt["attempt_id"]
        assert fake_llm.json_calls == calls
        question = nxt

    last = await client.post(
        "/api/exams/answer",
        headers=acct.headers,
        json={"attempt_id": question["attempt_id"], "answer_index": None},
    )
    assert last.json()["finished"] is True
    assert "correct" not in last.json()  # correction dévoilée seulement à /finish

    finish = await client.post(f"/api/exams/{start['exam_id']}/finish", headers=acct.headers)
    assert finish.status_code == 200
    result = finish.json()
    assert result["total"] == 3 and result["correct_count"] == 2
    assert result["score"] == round(2 / 3, 4)
    assert len(result["details"]) == 3

    again_finish = await client.post(f"/api/exams/{start['exam_id']}/finish", headers=acct.headers)
    assert again_finish.json()["score"] == result["score"]
    assert (await _profile(acct)).total_sessions == 1  # profil mis à jour une seule fois

    history = await client.get("/api/exams/history", headers=acct.headers)
    assert [e["exam_id"] for e in history.json()] == [start["exam_id"]]
    late = await client.post(
        "/api/exams/answer",
        headers=acct.headers,
        json={"attempt_id": question["attempt_id"], "answer_index": 1},
    )
    assert late.status_code == 409  # examen terminé


async def test_exam_answer_after_deadline_is_refused(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    from datetime import timedelta

    from sqlalchemy import update

    from app.core.timeutil import utcnow
    from app.models.models import ExamSession

    acct = await signup()
    start = await _start_exam(client, acct)
    async with dbmod.AsyncSessionLocal() as s:
        await s.execute(update(ExamSession).values(started_at=utcnow() - timedelta(hours=2)))
        await s.commit()
    r = await client.post(
        "/api/exams/answer",
        headers=acct.headers,
        json={"attempt_id": start["first_question"]["attempt_id"], "answer_index": 1},
    )
    assert r.json()["time_expired"] is True and r.json()["finished"] is True
