"""Fiabilité du BKT, révision espacée, prérequis, aide socratique, clés de QCM, banque, confiance."""

from collections.abc import Callable
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core import llm
from app.core.config import settings
from app.core.timeutil import utcnow
from app.db import database as dbmod
from app.models.models import ExerciseAttempt, LearnerProfile, QuestionBankItem, QuizAttempt
from app.services import metacognition, question_bank, quiz_service
from app.services.adaptive_service import AdaptiveLearningService, MasteryTracker
from app.services.rag_service import bm25_rank, extract_relevant_sections
from app.services.topics import canonical_topic, resolve_topic, weak_prerequisites
from app.services.tutor_service import is_stuck_message, socratic_escalation

service = AdaptiveLearningService()


def make_profile(**overrides: object) -> SimpleNamespace:
    base: dict[str, Any] = dict(
        total_questions=0,
        total_sessions=0,
        streak_days=0,
        last_activity=None,
        subject_scores={},
        concept_mastery={},
        concept_last_practiced={},
        concept_stats={},
        updated_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ───────────── BKT ─────────────


def test_mcq_success_is_weaker_evidence_than_open_success() -> None:
    mcq = MasteryTracker.update(0.30, True, "mcq")
    open_ = MasteryTracker.update(0.30, True, "open")
    assert mcq == pytest.approx(0.69, abs=0.01)
    assert open_ == pytest.approx(0.91, abs=0.01)
    assert mcq < MasteryTracker.update(0.30, True)  # avant : le même hasard 0,10 surestimait le QCM


def test_hints_and_low_confidence_lower_the_evidence_of_a_success() -> None:
    plain = MasteryTracker.update(0.3, True, "mcq")
    assert (
        MasteryTracker.update(0.3, True, "mcq", hints_used=2)
        < MasteryTracker.update(0.3, True, "mcq", hints_used=1)
        < plain
    )
    assert MasteryTracker.update(0.3, True, "mcq", confidence=1) < plain
    assert MasteryTracker.update(0.3, True, "mcq", confidence=2) == plain
    assert MasteryTracker.update(0.3, True, "mcq", confidence=3) == plain


@pytest.mark.parametrize("hints", [0, 3, 50])
@pytest.mark.parametrize("item_type", [None, "mcq", "open"])
def test_update_stays_in_unit_interval_with_any_options(hints: int, item_type: str | None) -> None:
    for prior in (0.0, 0.5, 1.0):
        for correct in (True, False):
            assert 0.0 <= MasteryTracker.update(prior, correct, item_type, hints, 1) <= 1.0


def test_forgetting_decays_toward_the_floor_never_below() -> None:
    assert MasteryTracker.apply_forgetting(0.9, 0, floor=0.3) == 0.9
    assert 0.3 < MasteryTracker.apply_forgetting(0.9, 60, floor=0.3) < 0.9
    assert MasteryTracker.apply_forgetting(0.2, 100, floor=0.3) == 0.2  # déjà sous le plancher : inchangé
    assert MasteryTracker.apply_forgetting(0.9, 30, stability=120) > MasteryTracker.apply_forgetting(
        0.9, 30, stability=10
    )


def test_stability_grows_on_success_and_shrinks_on_failure() -> None:
    assert MasteryTracker.next_stability(30, True) == 60
    assert MasteryTracker.next_stability(30, True, hints_used=1) == 36
    assert MasteryTracker.next_stability(30, False) == 15
    assert MasteryTracker.next_stability(3, False) == MasteryTracker.MIN_STABILITY_DAYS
    assert MasteryTracker.next_stability(300, True) == MasteryTracker.MAX_STABILITY_DAYS


def test_profile_update_forgets_before_updating_and_tracks_stats() -> None:
    long_ago = (utcnow() - timedelta(days=300)).isoformat()
    profile = make_profile(
        concept_mastery={"mathematiques": {"x": 0.9}},
        concept_last_practiced={"mathematiques": {"x": long_ago}},
    )
    service.update_profile_after_interaction(
        profile, "mathematiques", "x", is_correct=False, item_type="open"
    )  # type: ignore[arg-type]
    assert profile.concept_mastery["mathematiques"]["x"] < 0.5  # l'oubli a précédé l'échec
    stat = profile.concept_stats["mathematiques"]["x"]
    assert (
        stat["attempts"] == 1
        and stat["correct"] == 0
        and stat["stability"] < MasteryTracker.FORGETTING_TAU_DAYS
    )


def test_subject_score_is_weighted_by_attempts() -> None:
    profile = make_profile(
        concept_mastery={"mathematiques": {"a": 0.9, "b": 0.1}},
        concept_stats={"mathematiques": {"a": {"attempts": 9}, "b": {"attempts": 1}}},
    )
    service.update_profile_after_interaction(profile, "mathematiques", "a", is_correct=True)  # type: ignore[arg-type]
    simple_mean = sum(profile.concept_mastery["mathematiques"].values()) / 2
    assert profile.subject_scores["mathematiques"] > simple_mean  # le concept très pratiqué pèse plus


def test_math_expert_badge_needs_breadth_and_volume() -> None:
    narrow = make_profile(
        subject_scores={"mathematiques": 0.95}, concept_stats={"mathematiques": {"a": {"attempts": 1}}}
    )
    broad = make_profile(
        subject_scores={"mathematiques": 0.95},
        concept_stats={"mathematiques": {"a": {"attempts": 5}, "b": {"attempts": 5}, "c": {"attempts": 1}}},
    )
    assert "math_expert" not in {b.code for b in service.check_and_award_badges(narrow, [])}  # type: ignore[arg-type]
    assert "math_expert" in {b.code for b in service.check_and_award_badges(broad, [])}  # type: ignore[arg-type]


def test_concept_level_falls_back_to_subject_then_default() -> None:
    profile = make_profile(concept_mastery={"mathematiques": {"a": 0.4, "b": 0.6}})
    assert service.concept_level(profile, "mathematiques", "a") == 0.4  # type: ignore[arg-type]
    assert service.concept_level(profile, "mathematiques", "inconnu") == pytest.approx(0.5)  # type: ignore[arg-type]
    assert service.concept_level(make_profile(), "physique", "x") == 0.5  # type: ignore[arg-type]


# ───────────── Répétition espacée, thèmes, prérequis ─────────────


def test_due_reviews_flag_learned_concepts_about_to_be_forgotten() -> None:
    old = (utcnow() - timedelta(days=20)).isoformat()
    profile = make_profile(
        concept_mastery={"mathematiques": {"fractions": 0.85, "faible": 0.2}},
        concept_last_practiced={"mathematiques": {"fractions": old, "faible": old}},
        concept_stats={"mathematiques": {"fractions": {"stability": 30}}},
    )
    due = service.get_due_reviews(profile)  # type: ignore[arg-type]
    assert [d["concept"] for d in due] == ["fractions"]  # le concept faible n'est pas « appris »
    recs = service.get_recommendations(profile)  # type: ignore[arg-type]
    review = next(r for r in recs if r["concept"] == "fractions")
    assert "répétition espacée" in review["reason"] and "%" in review["reason"]
    en = service.get_recommendations(profile, lang="en")  # type: ignore[arg-type]
    assert any("spaced repetition" in r["reason"] for r in en)


def test_recently_practiced_concepts_are_not_due() -> None:
    recent = (utcnow() - timedelta(hours=2)).isoformat()
    profile = make_profile(
        concept_mastery={"mathematiques": {"fractions": 0.9}},
        concept_last_practiced={"mathematiques": {"fractions": recent}},
    )
    assert service.get_due_reviews(profile) == []  # type: ignore[arg-type]


def test_resolve_topic_maps_variants_to_the_stored_key() -> None:
    assert resolve_topic(["fractions"], "Les fractions") == "fractions"
    assert resolve_topic(["fractions"], "fractoins") == "fractions"  # faute de frappe
    assert resolve_topic(["Équations 2nd degré"], "equations 2nd degre") == "Équations 2nd degré"
    assert resolve_topic(["fractions"], "géométrie") == "géométrie"  # inconnu : inchangé
    assert resolve_topic([], "  Les   suites ") == "Les suites"
    assert canonical_topic("L'Énergie") == canonical_topic("energie")


def test_weak_prerequisite_changes_the_recommended_action() -> None:
    profile = make_profile(
        concept_mastery={"mathematiques": {"Équations 2nd degré": 0.4, "Équations 1er degré": 0.1}}
    )
    assert weak_prerequisites(
        "mathematiques", "Équations 2nd degré", {"Équations 2nd degré": 0.4, "Équations 1er degré": 0.1}
    ) == ["Équations 1er degré"]
    recs = service.get_recommendations(profile)  # type: ignore[arg-type]
    action = next(r["action"] for r in recs if r["concept"] == "Équations 2nd degré")
    assert action == "Exercices sur Équations 1er degré, puis Équations 2nd degré"
    # Un prérequis jamais pratiqué n'est pas accusé.
    assert weak_prerequisites("mathematiques", "Équations 2nd degré", {"Équations 2nd degré": 0.4}) == []


# ───────────── Aide socratique ─────────────


@pytest.mark.parametrize(
    "text", ["Je ne sais pas", "jsp", "je suis bloqué", "I'm stuck", "no idea", "Je ne comprends pas"]
)
def test_stuck_messages_are_detected(text: str) -> None:
    assert is_stuck_message(text)


@pytest.mark.parametrize(
    "text",
    [
        "x = 4 ?",
        "Je pense que c'est 12",
        "bonjour",
        "Pourquoi 2+2 = 4 alors que je pensais à la somme de deux fractions simples et leurs dénominateurs, je ne sais pas ?",
    ],
)
def test_normal_or_long_messages_are_not_stuck(text: str) -> None:
    assert not is_stuck_message(text)


def test_socratic_help_escalates_but_never_without_a_stuck_message() -> None:
    history: list[Any] = [
        {"role": "user", "content": "Résous 2x+3=7"},
        {"role": "assistant", "content": "Que ferais-tu en premier ?"},
    ]
    assert socratic_escalation(history, "x = 4 ?") == 0
    assert socratic_escalation(history, "je ne sais pas") == 1
    history += [
        {"role": "user", "content": "je ne sais pas"},
        {"role": "assistant", "content": "Un indice : ..."},
    ]
    assert socratic_escalation(history, "toujours bloqué") == 2
    assert socratic_escalation(history, "ah, je soustrais 3 ?") == 0  # il repart : on revient à une question


# ───────────── RAG BM25 ─────────────


def test_bm25_prefers_the_section_where_rare_words_concentrate() -> None:
    kb = "# Acides\nLe pH mesure l'acidité.\n\n# Divers\nTexte sur l'ADN et autre chose, avec un peu de pH."
    ranked = bm25_rank(kb.split("\n\n"), "quel est le pH ?")
    assert ranked and ranked[0][1].startswith("# Acides")  # sigle court « pH » conservé


def test_rag_returns_nothing_when_nothing_matches_and_truncates_long_sections() -> None:
    assert extract_relevant_sections("# A\nrien ici", "zzzzzz inconnu") == ""
    long_section = "# Gros\n" + "pH acide base " * 500
    out = extract_relevant_sections(long_section, "calcul du pH", max_chars=300)
    assert 0 < len(out) <= 300


# ───────────── Clé de QCM ─────────────


async def test_key_verification_discards_questions_whose_key_is_contradicted(
    fake_llm: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "QUIZ_VERIFY_KEYS", True)
    fake_llm.verifier_answer = 1  # d'accord avec la clé (index 1)
    ok = await quiz_service.generate_question("mathematiques", "college", "Additions")
    assert ok.correct_index == 1
    fake_llm.verifier_answer = 3  # désaccord → question écartée, 2 essais, puis erreur
    with pytest.raises(llm.LLMError, match="n'a pas réussi"):
        await quiz_service.generate_question("mathematiques", "college", "Additions")
    fake_llm.verifier_answer = -1  # ambigu
    with pytest.raises(llm.LLMError, match="n'a pas réussi"):
        await quiz_service.generate_question("mathematiques", "college", "Additions")


async def test_key_verification_fails_open_when_the_verifier_breaks(
    fake_llm: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "QUIZ_VERIFY_KEYS", True)
    fake_llm.verifier_answer = "n'importe quoi"  # sortie inexploitable
    question = await quiz_service.generate_question("mathematiques", "college", "Additions")
    assert question.correct_index == 1


# ───────────── Confiance et banque (API) ─────────────

QUIZ = {"subject": "mathematiques", "level": "college", "topic": "Fractions"}


async def _ask(client: AsyncClient, acct: Any) -> dict[str, Any]:
    r = await client.get("/api/quiz/generate", headers=acct.headers, params=QUIZ)
    assert r.status_code == 200, r.text
    return r.json()


async def test_confidence_is_stored_and_reported_back(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    acct = await signup()
    q = await _ask(client, acct)
    wrong = await client.post(
        "/api/quiz/answer",
        headers=acct.headers,
        json={"question_id": q["id"], "answer_index": 0, "confidence": 3},
    )
    assert wrong.status_code == 200 and wrong.json()["calibration"] == "overconfident"
    again = await client.post(
        "/api/quiz/answer",
        headers=acct.headers,
        json={"question_id": q["id"], "answer_index": 0, "confidence": 1},
    )
    assert again.json()["calibration"] == "overconfident"  # première réponse conservée
    q2 = await _ask(client, acct)
    lucky = await client.post(
        "/api/quiz/answer",
        headers=acct.headers,
        json={"question_id": q2["id"], "answer_index": 1, "confidence": 1},
    )
    assert lucky.json()["calibration"] == "underconfident"
    q3 = await _ask(client, acct)
    plain = await client.post(
        "/api/quiz/answer", headers=acct.headers, json={"question_id": q3["id"], "answer_index": 1}
    )
    assert plain.json()["calibration"] is None


async def test_confidence_out_of_range_is_rejected(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    acct = await signup()
    q = await _ask(client, acct)
    r = await client.post(
        "/api/quiz/answer",
        headers=acct.headers,
        json={"question_id": q["id"], "answer_index": 1, "confidence": 4},
    )
    assert r.status_code == 422


async def test_low_confidence_success_counts_for_less_in_the_profile(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    sure, unsure = await signup("alice"), await signup("bob")
    for acct, confidence in ((sure, 3), (unsure, 1)):
        q = await _ask(client, acct)
        await client.post(
            "/api/quiz/answer",
            headers=acct.headers,
            json={"question_id": q["id"], "answer_index": 1, "confidence": confidence},
        )
    async with dbmod.AsyncSessionLocal() as s:
        scores = [
            p.concept_mastery["mathematiques"]["Fractions"]
            for p in (await s.execute(select(LearnerProfile))).scalars()
        ]
    assert len(scores) == 2 and min(scores) < max(scores)


async def test_calibration_summary_needs_enough_answers(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    acct = await signup()
    empty = (await client.get("/api/quiz/calibration", headers=acct.headers)).json()
    assert empty == {"answered": 0, "overconfident_rate": 0.0, "underconfident_rate": 0.0, "label": None}
    for _ in range(metacognition.MIN_SAMPLE):
        q = await _ask(client, acct)
        await client.post(
            "/api/quiz/answer",
            headers=acct.headers,
            json={"question_id": q["id"], "answer_index": 0, "confidence": 3},
        )
    summary = (await client.get("/api/quiz/calibration", headers=acct.headers)).json()
    assert summary["answered"] == metacognition.MIN_SAMPLE
    assert summary["label"] == "overconfident" and summary["overconfident_rate"] == 1.0


async def test_calibration_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/quiz/calibration")).status_code == 401


async def test_question_bank_fills_then_serves_without_any_llm_call(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "QUESTION_BANK_ENABLED", True)
    monkeypatch.setattr(settings, "QUESTION_BANK_MIN_UNSEEN", 2)
    teacher = await signup("alice")
    for _ in range(3):  # alice remplit la banque (3 questions générées)
        await _ask(client, teacher)
    async with dbmod.AsyncSessionLocal() as s:
        assert len((await s.execute(select(QuestionBankItem))).scalars().all()) == 3
    calls = fake_llm.json_calls
    student = await signup("bob")
    served = await _ask(client, student)
    assert fake_llm.json_calls == calls  # servie depuis la banque : aucun appel IA
    async with dbmod.AsyncSessionLocal() as s:
        attempt = await s.get(QuizAttempt, served["id"])
        assert attempt is not None and attempt.bank_id is not None
    # Réponse : les statistiques de l'item sont mises à jour.
    await client.post(
        "/api/quiz/answer", headers=student.headers, json={"question_id": served["id"], "answer_index": 1}
    )
    async with dbmod.AsyncSessionLocal() as s:
        item = await s.get(QuestionBankItem, attempt.bank_id)
        assert item is not None and item.served == 1 and item.correct == 1


async def test_bank_never_repeats_a_question_to_the_same_student(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "QUESTION_BANK_ENABLED", True)
    monkeypatch.setattr(settings, "QUESTION_BANK_MIN_UNSEEN", 1)
    acct = await signup()
    seen: set[str] = set()
    for _ in range(4):
        q = await _ask(client, acct)
        assert q["question"] not in seen
        seen.add(q["question"])


async def test_suspect_items_are_withdrawn(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "QUESTION_BANK_ENABLED", True)
    monkeypatch.setattr(settings, "QUESTION_BANK_SUSPECT_MIN_SERVED", 3)
    acct = await signup()
    q = await _ask(client, acct)
    async with dbmod.AsyncSessionLocal() as s:
        bank_id = (await s.get(QuizAttempt, q["id"])).bank_id  # type: ignore[union-attr]
        for _ in range(3):  # trois échecs sur trois : taux 0 % < seuil
            await question_bank.record_outcome(s, bank_id, False)
        await s.commit()
        item = await s.get(QuestionBankItem, bank_id)
        assert item is not None and item.suspect is True


def test_question_hash_ignores_case_accents_and_spacing() -> None:
    assert question_bank.question_hash("Quelle est la dérivée ?") == question_bank.question_hash(
        "  quelle  est la derivee ?"
    )


# ───────────── Indices (exercices) ─────────────


async def test_hints_used_is_stored_and_capped_by_the_exercise_hints(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    acct = await signup()
    ex = (
        await client.post(
            "/api/exercises/generate",
            headers=acct.headers,
            json={"subject": "mathematiques", "level": "college", "topic": "Additions"},
        )
    ).json()
    r = await client.post(
        "/api/exercises/submit",
        headers=acct.headers,
        json={"exercise_id": ex["id"], "answer": "4", "hints_used": 9},
    )
    assert r.status_code == 200
    async with dbmod.AsyncSessionLocal() as s:
        attempt = (await s.execute(select(ExerciseAttempt))).scalars().one()
        assert attempt.hints_used == 1  # l'exercice n'avait qu'un indice : plafonné


async def test_hints_used_validation(client: AsyncClient, signup: Callable[..., Any], fake_llm: Any) -> None:
    acct = await signup()
    r = await client.post(
        "/api/exercises/submit",
        headers=acct.headers,
        json={"exercise_id": "x", "answer": "4", "hints_used": -1},
    )
    assert r.status_code == 422
