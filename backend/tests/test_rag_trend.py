"""RAG insensible aux accents et tendance de progression."""

from app.api.progress import compute_trend
from app.services.rag_service import extract_relevant_sections, normalize_text

KB = "# Intro\nBienvenue\n\n# Dérivées\nLa dérivée d'une fonction mesure sa variation.\n\n# Autre\nSans rapport."


def test_normalize_removes_accents_and_case() -> None:
    assert normalize_text("Dérivée Été") == "derivee ete"


def test_rag_finds_accented_section_from_unaccented_query() -> None:
    out = extract_relevant_sections(KB, "explique la derivee")
    assert "mesure sa variation" in out
    assert "Sans rapport" not in out


def test_trend_requires_data_in_both_windows() -> None:
    assert compute_trend([0.9], []) == "stable"
    assert compute_trend([], [0.4]) == "stable"


def test_trend_up_down_stable() -> None:
    assert compute_trend([0.7, 0.8], [0.4, 0.5]) == "up"
    assert compute_trend([0.3], [0.6]) == "down"
    assert compute_trend([0.52], [0.5]) == "stable"
