"""BKT, oubli, série de jours (fuseau local) et badges."""

from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.core.timeutil import utcnow
from app.services.adaptive_service import AdaptiveLearningService, MasteryTracker

service = AdaptiveLearningService()


def make_profile(**overrides: object) -> SimpleNamespace:
    base = dict(
        total_questions=0,
        total_sessions=0,
        streak_days=0,
        last_activity=None,
        subject_scores={},
        concept_mastery={},
        concept_last_practiced={},
        updated_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_correct_answer_raises_mastery_and_wrong_lowers_it() -> None:
    prior = 0.5
    assert MasteryTracker.update(prior, True) > prior
    assert MasteryTracker.update(prior, False) < MasteryTracker.update(prior, True)


@pytest.mark.parametrize("prior", [0.0, 0.01, 0.3, 0.99, 1.0])
@pytest.mark.parametrize("correct", [True, False])
def test_mastery_stays_in_unit_interval(prior: float, correct: bool) -> None:
    assert 0.0 <= MasteryTracker.update(prior, correct) <= 1.0


def test_repeated_success_converges_to_high_mastery() -> None:
    value = 0.3
    for _ in range(10):
        value = MasteryTracker.update(value, True)
    assert value > 0.9


def test_forgetting_decays_with_time_and_never_increases() -> None:
    assert MasteryTracker.apply_forgetting(0.8, 0) == 0.8
    assert MasteryTracker.apply_forgetting(0.8, 30) < MasteryTracker.apply_forgetting(0.8, 10) < 0.8
    assert MasteryTracker.apply_forgetting(0.8, -5) == 0.8  # jours négatifs ignorés


def test_profile_update_tracks_concept_and_subject_score() -> None:
    profile = make_profile()
    service.update_profile_after_interaction(profile, "mathematiques", "fractions", is_correct=True)  # type: ignore[arg-type]
    assert profile.total_questions == 1
    assert 0 < profile.concept_mastery["mathematiques"]["fractions"] <= 1
    assert profile.subject_scores["mathematiques"] == profile.concept_mastery["mathematiques"]["fractions"]
    assert profile.streak_days == 1


def test_new_session_flag_counts_sessions_not_questions() -> None:
    profile = make_profile()
    service.update_profile_after_interaction(profile, "physique", "x", score=0.7, new_session=True)  # type: ignore[arg-type]
    service.update_profile_after_interaction(profile, "physique", "x", score=0.7)  # type: ignore[arg-type]
    assert profile.total_sessions == 1 and profile.total_questions == 2


def test_streak_increments_next_day_resets_after_gap_and_holds_same_day() -> None:
    profile = make_profile(streak_days=3, last_activity=utcnow() - timedelta(days=1))
    service.update_profile_after_interaction(profile, "physique", "x", is_correct=True)  # type: ignore[arg-type]
    assert profile.streak_days == 4
    service.update_profile_after_interaction(profile, "physique", "x", is_correct=True)  # type: ignore[arg-type]
    assert profile.streak_days == 4  # même jour : inchangé

    old = make_profile(streak_days=9, last_activity=utcnow() - timedelta(days=5))
    service.update_profile_after_interaction(old, "physique", "x", is_correct=True)  # type: ignore[arg-type]
    assert old.streak_days == 1


def test_effective_mastery_applies_forgetting() -> None:
    long_ago = (utcnow() - timedelta(days=60)).isoformat()
    profile = make_profile(
        concept_mastery={"mathematiques": {"fractions": 0.9}},
        concept_last_practiced={"mathematiques": {"fractions": long_ago}},
    )
    effective = service.get_effective_mastery(profile)  # type: ignore[arg-type]
    # L'oubli décroît vers l'a priori (0,30), jamais en dessous : un concept oublié vaut un concept inconnu.
    assert MasteryTracker.P_INIT <= effective["mathematiques"]["fractions"] < MasteryTracker.P_INIT + 0.1


def test_recommendations_prioritise_weak_concepts() -> None:
    profile = make_profile(
        concept_mastery={"mathematiques": {"fractions": 0.2, "geometrie": 0.9}},
        subject_scores={"mathematiques": 0.55},
    )
    recs = service.get_recommendations(profile)  # type: ignore[arg-type]
    assert recs[0]["priority"] == "high" and recs[0]["concept"] == "fractions"
    assert any(r["priority"] == "medium" for r in recs)


def test_zpd_difficulty_thresholds() -> None:
    assert [service.get_zpd_difficulty(x) for x in (0.1, 0.4, 0.7, 0.95)] == [
        "debutant",
        "intermediaire",
        "avance",
        "expert",
    ]


def test_badges_are_awarded_once_and_perfect_score_uses_context() -> None:
    profile = make_profile(total_sessions=1, streak_days=7, subject_scores={"francais": 0.8, "anglais": 0.75})
    earned = {b.code for b in service.check_and_award_badges(profile, [])}  # type: ignore[arg-type]
    assert {"first_session", "streak_7", "polyglot"} <= earned
    assert "perfect_score" not in earned
    again = {b.code for b in service.check_and_award_badges(profile, list(earned))}  # type: ignore[arg-type]
    assert again == set()
    perfect = {b.code for b in service.check_and_award_badges(profile, [], context={"exercise_score": 1.0})}  # type: ignore[arg-type]
    assert "perfect_score" in perfect


def test_bkt_parameters_are_the_single_source_of_truth() -> None:
    """Les simulations doivent importer ``MasteryTracker`` (pas de copie des paramètres)."""
    assert 0 < MasteryTracker.P_INIT < 1
    assert not hasattr(MasteryTracker, "P_FORGET")  # l'oubli est une décroissance à part
    assert MasteryTracker.apply_forgetting(0.8, 30) == pytest.approx(0.8 * 0.3679, abs=1e-3)
