"""Grille de correction : validation, renormalisation, score calculé côté serveur."""

import pytest

from app.services.exercise_service import (
    DEFAULT_RUBRIC,
    clean_numeric_answer,
    normalize_rubric,
    validate_exercise,
)
from app.services.tutor_service import aggregate_rubric_score

RUBRIC = [{"critere": "Méthode", "points": 0.6}, {"critere": "Résultat", "points": 0.4}]


def test_default_rubric_sums_to_one() -> None:
    assert sum(c["points"] for c in DEFAULT_RUBRIC) == pytest.approx(1.0)


@pytest.mark.parametrize("bad", [None, "texte", [], [{"critere": "seul", "points": 1}], [{"x": 1}], 42])
def test_invalid_rubrics_fall_back_to_default(bad: object) -> None:
    assert normalize_rubric(bad) == DEFAULT_RUBRIC


def test_rubric_points_are_renormalised_to_one() -> None:
    result = normalize_rubric([{"critere": "A", "points": 2}, {"critere": "B", "points": 6}])
    assert sum(c["points"] for c in result) == pytest.approx(1.0)
    assert result[0]["critere"] == "A" and result[0]["points"] == pytest.approx(0.25)


def test_negative_and_non_numeric_points_are_dropped() -> None:
    result = normalize_rubric(
        [
            {"critere": "A", "points": "x"},
            {"critere": "B", "points": -1},
            {"critere": "C", "points": 0.5},
            {"critere": "D", "points": 0.5},
        ]
    )
    assert [c["critere"] for c in result] == ["C", "D"]


def test_score_is_weighted_sum_computed_by_server() -> None:
    parsed = {
        "rubric_scores": [
            {"critere": "Méthode", "taux": 1.0, "justification": "bien"},
            {"critere": "Résultat", "taux": 0.5, "justification": "à moitié"},
        ],
        "feedback": "Bravo",
    }
    result = aggregate_rubric_score(parsed, RUBRIC)
    assert result["score"] == pytest.approx(0.8)
    assert result["correct"] is True and result["partial"] is False
    assert [b["points_obtenus"] for b in result["rubric_breakdown"]] == [
        pytest.approx(0.6),
        pytest.approx(0.2),
    ]


def test_missing_or_out_of_range_rates_are_handled() -> None:
    parsed = {"rubric_scores": [{"critere": "Méthode", "taux": 7}, {"critere": "Inconnu", "taux": 1}]}
    result = aggregate_rubric_score(parsed, RUBRIC)
    assert result["score"] == pytest.approx(0.6)  # taux borné à 1, critère manquant = 0
    assert "non évalué" in result["rubric_breakdown"][1]["justification"]


def test_garbage_rates_never_crash() -> None:
    parsed = {
        "rubric_scores": [{"critere": "Méthode", "taux": "beaucoup"}, {"critere": "Résultat", "taux": None}],
        "errors": "oops",
    }
    result = aggregate_rubric_score(parsed, RUBRIC)
    assert result["score"] == 0.0 and result["errors"] == []


def test_two_equivalent_answers_get_equal_scores() -> None:
    parsed = {"rubric_scores": [{"critere": "Méthode", "taux": 0.7}, {"critere": "Résultat", "taux": 0.7}]}
    assert (
        aggregate_rubric_score(parsed, RUBRIC)["score"]
        == aggregate_rubric_score(dict(parsed), RUBRIC)["score"]
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (4, "4"),
        (12.5, "12.5"),
        ("  7 ", "7"),
        ("", None),
        (None, None),
        (True, None),
        ([1], None),
        ({"a": 1}, None),
    ],
)
def test_numeric_answer_accepts_any_json_type(raw: object, expected: str | None) -> None:
    """Régression de l'audit : un entier JSON faisait planter `.strip()`."""
    assert clean_numeric_answer(raw) == expected


def test_validate_exercise_rejects_empty_and_accepts_numeric_int() -> None:
    assert validate_exercise({"statement": "", "solution": "x"}) is None
    ok = validate_exercise(
        {"statement": "Calcule 2+2 maintenant", "solution": "4", "numeric_answer": 4, "estimated_min": "abc"}
    )
    assert ok is not None and ok.numeric_answer == "4" and ok.estimated_min == 10
