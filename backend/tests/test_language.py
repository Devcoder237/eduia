"""Bilinguisme de bout en bout : la langue demandée atteint chaque générateur et chaque message."""

import ast
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import AsyncClient

from app.core import i18n
from app.core.i18n import (
    SUBJECT_NAMES,
    known_french_messages,
    language_rule,
    localize_badge,
    parse_lang,
    subject_name,
    translate_detail,
)
from app.core.timeutil import today_local
from app.services.adaptive_service import adaptive_service
from app.services.math_verify import verify_numeric_answer

EN = {"Accept-Language": "en"}
FR = {"Accept-Language": "fr"}
RULE_EN = "LANGUAGE RULE"
RULE_FR = "REGLE DE LANGUE"


# --- Lecture de l'en-tête -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "fr"),
        ("", "fr"),
        ("fr", "fr"),
        ("fr-CA", "fr"),
        ("en", "en"),
        ("en-US,en;q=0.9", "en"),
        ("EN-gb", "en"),
        ("de-DE,de;q=0.9", "fr"),  # langue non gérée : défaut
        ("de,en;q=0.5", "en"),  # première langue SUPPORTÉE
        ("fr;q=0.3,en;q=0.8", "en"),  # priorités respectées
        ("en;q=abc", "fr"),  # q invalide => 0 : retombe sur le défaut
        (";;,,", "fr"),
    ],
)
def test_parse_lang(header: str | None, expected: str) -> None:
    assert parse_lang(header) == expected


# --- Règle de langue des prompts ----------------------------------------------------------


def test_language_rule_french_keeps_historical_behaviour() -> None:
    rule = language_rule("fr", "mathematiques")
    assert RULE_FR in rule and "francais" in rule and RULE_EN not in rule


def test_language_rule_english_overrides_french_instructions() -> None:
    rule = language_rule("en", "mathematiques")
    assert RULE_EN in rule and "ENGLISH" in rule and "JSON keys EXACTLY" in rule
    assert "Subject = English" in language_rule("en", "anglais")
    assert "quote the French" in language_rule("en", "francais")


# --- Messages d'erreur --------------------------------------------------------------------


def test_translate_detail_exact_pattern_and_fallback() -> None:
    assert translate_detail("Exercice introuvable.", "fr") == "Exercice introuvable."
    assert translate_detail("Exercice introuvable.", "en") == "Exercise not found."
    assert (
        translate_detail("Fichier trop volumineux (10 Mo maximum).", "en")
        == "File too large (10 MB maximum)."
    )
    assert translate_detail("La date cible est trop lointaine (60 jours maximum).", "en") == (
        "The target date is too far away (60 days maximum)."
    )
    assert translate_detail("Le nouveau mot de passe doit contenir au moins un chiffre.", "en") == (
        "The new password must contain at least one digit."
    )
    assert translate_detail("Message inconnu", "en") == "Message inconnu"


def _literal_messages() -> set[str]:
    """Tous les messages français littéraux envoyés au client (detail=…, _unavailable, _fail…)."""
    found: set[str] = set()
    app_dir = Path(i18n.__file__).resolve().parent.parent
    for path in app_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if (
                    kw.arg == "detail"
                    and isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ):
                    found.add(kw.value.value)
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name in {"_unavailable", "_fail"} and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    found.add(first.value)
    return found


def test_every_literal_server_message_has_an_english_translation() -> None:
    missing = sorted(m for m in _literal_messages() if m not in known_french_messages())
    assert missing == [], f"Messages sans traduction anglaise : {missing}"


def test_translations_are_not_identical_to_the_source() -> None:
    for french in known_french_messages():
        assert translate_detail(french, "en") != french


async def test_http_errors_follow_the_requested_language(
    client: AsyncClient, signup: Callable[..., Any]
) -> None:
    acct = await signup()
    body = {"exercise_id": "inexistant", "answer": "4"}
    fr = await client.post("/api/exercises/submit", headers={**acct.headers, **FR}, json=body)
    en = await client.post("/api/exercises/submit", headers={**acct.headers, **EN}, json=body)
    none = await client.post("/api/exercises/submit", headers=acct.headers, json=body)
    assert fr.status_code == en.status_code == none.status_code == 404
    assert fr.json()["detail"] == "Exercice introuvable."
    assert none.json()["detail"] == "Exercice introuvable."  # sans en-tête : français (historique)
    assert en.json()["detail"] == "Exercise not found."


async def test_unauthenticated_error_is_translated(client: AsyncClient) -> None:
    r = await client.get("/api/progress/dashboard", headers=EN)
    assert r.status_code in {401, 403}
    assert "sign in" in r.json()["detail"].lower() or "session" in r.json()["detail"].lower()


# --- Génération IA ------------------------------------------------------------------------


async def _session(client: AsyncClient, acct: Any) -> str:
    r = await client.post(
        "/api/chat/session",
        headers=acct.headers,
        json={"subject": "mathematiques", "level": "lycee", "mode": "explain"},
    )
    return str(r.json()["session_id"])


@pytest.mark.parametrize(
    ("headers", "rule", "absent"), [(EN, RULE_EN, RULE_FR), (FR, RULE_FR, RULE_EN), ({}, RULE_FR, RULE_EN)]
)
async def test_tutor_stream_and_message_prompts_follow_language(
    client: AsyncClient,
    signup: Callable[..., Any],
    fake_llm: Any,
    headers: dict[str, str],
    rule: str,
    absent: str,
) -> None:
    acct = await signup()
    sid = await _session(client, acct)
    payload = {
        "session_id": sid,
        "message": "Explain derivatives",
        "subject": "mathematiques",
        "level": "lycee",
    }
    streamed = await client.post("/api/chat/stream", headers={**acct.headers, **headers}, json=payload)
    assert streamed.status_code == 200
    assert rule in fake_llm.last_system_prompt and absent not in fake_llm.last_system_prompt
    assert "TOUJOURS en francais" not in fake_llm.last_system_prompt  # consigne contradictoire retirée

    fake_llm.last_system_prompt = ""
    full = await client.post("/api/chat/message", headers={**acct.headers, **headers}, json=payload)
    assert full.status_code == 200
    assert rule in fake_llm.last_system_prompt


async def test_socratic_reminder_also_carries_the_english_rule(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import llm

    captured: list[list[llm.Message]] = []
    original = fake_llm.stream_text

    async def spy(messages: list[llm.Message]) -> Any:
        captured.append(messages)
        async for chunk in original(messages):
            yield chunk

    monkeypatch.setattr(llm, "stream_text", spy)
    acct = await signup()
    sid = (
        await client.post(
            "/api/chat/session",
            headers=acct.headers,
            json={"subject": "mathematiques", "level": "lycee", "mode": "socratic"},
        )
    ).json()["session_id"]
    await client.post(
        "/api/chat/stream",
        headers={**acct.headers, **EN},
        json={"session_id": sid, "message": "Help me", "subject": "mathematiques", "level": "lycee"},
    )
    system_messages = [m["content"] for m in captured[0] if m["role"] == "system"]
    assert any("socratique" in m and RULE_EN in m for m in system_messages)


async def test_stream_error_event_is_translated(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    fake_llm.stream_chunks = ["a", "b"]
    fake_llm.stream_error_after = 1
    acct = await signup()
    sid = await _session(client, acct)
    r = await client.post(
        "/api/chat/stream",
        headers={**acct.headers, **EN},
        json={"session_id": sid, "message": "Hi", "subject": "mathematiques", "level": "lycee"},
    )
    assert '"error"' in r.text  # le message du faux LLM est inconnu : conservé tel quel, sans plantage


@pytest.mark.parametrize(("headers", "rule", "absent"), [(EN, RULE_EN, RULE_FR), (FR, RULE_FR, RULE_EN)])
async def test_quiz_generation_follows_language(
    client: AsyncClient,
    signup: Callable[..., Any],
    fake_llm: Any,
    headers: dict[str, str],
    rule: str,
    absent: str,
) -> None:
    acct = await signup()
    r = await client.get(
        "/api/quiz/generate",
        headers={**acct.headers, **headers},
        params={"subject": "mathematiques", "level": "lycee", "topic": "Équations 2nd degré"},
    )
    assert r.status_code == 200
    prompt = fake_llm.json_prompts[-1]
    assert rule in prompt and absent not in prompt
    assert "Équations 2nd degré" in prompt  # le thème (identifiant) reste canonique


async def test_exercise_generation_and_correction_follow_language(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    acct = await signup()
    created = await client.post(
        "/api/exercises/generate",
        headers={**acct.headers, **EN},
        json={"subject": "mathematiques", "level": "college", "topic": "Additions"},
    )
    assert created.status_code == 200
    assert RULE_EN in fake_llm.json_prompts[-1]
    submitted = await client.post(
        "/api/exercises/submit",
        headers={**acct.headers, **EN},
        json={"exercise_id": created.json()["id"], "answer": "4"},
    )
    assert submitted.status_code == 200
    correction_prompt = fake_llm.json_prompts[-1]
    assert "rubric_scores" in correction_prompt and RULE_EN in correction_prompt
    assert "Automatic check" in submitted.json()["feedback"]  # note numérique en anglais
    assert "Vérification automatique" not in submitted.json()["feedback"]


async def test_exercise_french_correction_is_unchanged(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    acct = await signup()
    created = await client.post(
        "/api/exercises/generate",
        headers=acct.headers,
        json={"subject": "mathematiques", "level": "college", "topic": "Additions"},
    )
    submitted = await client.post(
        "/api/exercises/submit",
        headers=acct.headers,
        json={"exercise_id": created.json()["id"], "answer": "4"},
    )
    assert RULE_FR in fake_llm.json_prompts[-1]
    assert "Vérification automatique" in submitted.json()["feedback"]


async def test_exam_questions_follow_the_language_of_each_request(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    acct = await signup()
    start = await client.post(
        "/api/exams/start",
        headers={**acct.headers, **EN},
        json={
            "subject": "mathematiques",
            "level": "lycee",
            "exam_label": "Mock",
            "question_count": 3,
            "duration_min": 10,
            "request_id": "exam-lang-0001",
        },
    )
    assert start.status_code == 200, start.text
    assert RULE_EN in fake_llm.json_prompts[-1]
    nxt = await client.post(
        "/api/exams/answer",
        headers={**acct.headers, **EN},
        json={"attempt_id": start.json()["first_question"]["attempt_id"], "answer_index": 1},
    )
    assert nxt.status_code == 200
    assert RULE_EN in fake_llm.json_prompts[-1]


async def test_study_plan_prompt_and_fallback_follow_language(
    client: AsyncClient, signup: Callable[..., Any], fake_llm: Any
) -> None:
    acct = await signup()
    target = (today_local() + timedelta(days=3)).isoformat() + "T12:00:00Z"
    body = {"exam_label": "BEPC", "target_date": target, "subjects": ["mathematiques"], "level": "college"}
    ok = await client.post("/api/study-plans/generate", headers={**acct.headers, **EN}, json=body)
    assert ok.status_code == 200 and RULE_EN in fake_llm.json_prompts[-1]

    fake_llm.fail = True
    fallback_en = await client.post("/api/study-plans/generate", headers={**acct.headers, **EN}, json=body)
    assert fallback_en.status_code == 200
    plan = fallback_en.json()
    assert plan["days"][0]["day_label"] == "Day 1"
    assert plan["days"][0]["tasks"][0].startswith("Revise Mathematics")
    assert "simplified schedule" in (plan.get("notice") or "")

    fallback_fr = await client.post("/api/study-plans/generate", headers=acct.headers, json=body)
    assert fallback_fr.json()["days"][0]["day_label"] == "Jour 1"
    assert "planning simplifié" in (fallback_fr.json().get("notice") or "")


# --- Textes calculés côté serveur ---------------------------------------------------------


def _profile(**kw: Any) -> Any:
    return SimpleNamespace(
        concept_mastery=kw.get("mastery", {"mathematiques": {"Dérivées": 0.2}}),
        concept_last_practiced={},
        subject_scores=kw.get("scores", {"physique": 0.6}),
    )


def test_recommendations_follow_language() -> None:
    fr = adaptive_service.get_recommendations(_profile())
    en = adaptive_service.get_recommendations(_profile(), lang="en")
    assert [r["priority"] for r in fr] == [r["priority"] for r in en]  # mêmes données
    assert fr[0]["reason"].endswith("révision urgente") and en[0]["reason"].endswith("urgent review")
    assert en[0]["action"] == "Exercises on Dérivées" and fr[0]["action"] == "Exercices sur Dérivées"
    assert en[1]["action"] == "Strengthen Physics" and fr[1]["action"] == "Renforcement en physique"
    assert fr[0]["concept"] == en[0]["concept"] == "Dérivées"  # identifiant de donnée inchangé


def test_badges_are_localized_by_code() -> None:
    assert localize_badge("streak_7", "Semaine parfaite", "7 jours consécutifs", "fr") == (
        "Semaine parfaite",
        "7 jours consécutifs",
    )
    assert localize_badge("streak_7", "Semaine parfaite", "7 jours consécutifs", "en") == (
        "Perfect week",
        "7 days in a row",
    )
    assert localize_badge("inconnu", "Nom", "Desc", "en") == ("Nom", "Desc")  # badge inconnu : inchangé


def test_every_badge_rule_has_an_english_translation() -> None:
    from app.services.adaptive_service import BADGE_RULES

    for rule in BADGE_RULES:
        name, description = localize_badge(rule.code, rule.name, rule.description, "en")
        assert (name, description) != (rule.name, rule.description), rule.code


def test_numeric_check_notes_follow_language() -> None:
    fr = verify_numeric_answer("4", "Je trouve 5", "fr")
    en = verify_numeric_answer("4", "I get 5", "en")
    assert fr["match"] is en["match"] is False
    assert "NE correspond PAS" in fr["note"] and "does NOT match" in en["note"]
    assert "Automatic check not applicable" in verify_numeric_answer("x+1", "2", "en")["note"]
    assert verify_numeric_answer("4", "4")["note"].startswith("Vérification automatique")  # défaut = français


def test_subject_names_cover_every_subject_in_both_languages() -> None:
    assert set(SUBJECT_NAMES["fr"]) == set(SUBJECT_NAMES["en"])
    assert subject_name("physique", "en") == "Physics" and subject_name("inconnue", "en") == "inconnue"
