"""Vérification numérique exacte : signes, fractions, unités, calculs inachevés."""

import pytest

from app.services.math_verify import parse_expected, verify_numeric_answer


@pytest.mark.parametrize(
    ("expected", "student", "match"),
    [
        ("4", "x = 4", True),
        ("4", "je trouve 4.", True),
        ("-3", "x = -3", True),
        ("-3", "x = 3", False),
        ("8", "12 - 4 = 8", True),
        ("0.75", "donc 3/4", True),
        ("3/4", "0,75", True),
        ("12.5", "12,5 m", True),
        ("-2", "2 - 3 = -1 puis -2", True),
        ("4", "la réponse est 5", False),
        ("2", "5 - 3 = 2", True),
    ],
)
def test_checked_cases(expected: str, student: str, match: bool) -> None:
    result = verify_numeric_answer(expected, student)
    assert result["checked"] is True
    assert result["match"] is match


@pytest.mark.parametrize(
    ("expected", "student"),
    [
        ("12.5", "1250 cm"),  # conversion d'unité possible : non concluant, pas « faux »
        ("0.25", "25%"),
        ("2", "5 - 3"),  # calcul inachevé
        ("2", "5-3"),
        ("4", "je ne sais pas"),
        ("2x + 3", "2x + 3"),  # expression algébrique : hors périmètre
        ("", "4"),
    ],
)
def test_inconclusive_cases_never_claim_a_verdict(expected: str, student: str) -> None:
    result = verify_numeric_answer(expected, student)
    assert result["checked"] is False and result["match"] is None


def test_never_raises_on_hostile_input() -> None:
    for text in ("__import__('os').system('x')", "9" * 500, "1/0", "∞", "\x00", "-" * 1000):
        verify_numeric_answer("4", text)
        verify_numeric_answer(text, "4")


def test_parse_expected_exactness() -> None:
    assert parse_expected("1/3") is not None and parse_expected("1/3") * 3 == 1  # pas d'erreur de flottant
    assert parse_expected("1/0") is None
