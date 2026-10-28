"""Vérification exacte des réponses NUMÉRIQUES simples (filet de sécurité).

Périmètre volontairement restreint : seules les réponses attendues purement
numériques (entier, décimal, fraction : ``4``, ``12.5``, ``-3/4``) sont vérifiées.
Les expressions algébriques sont hors périmètre (``checked=False``) : mieux
vaut ne rien affirmer qu'une vérification qui se trompe en silence.

Décisions (correctifs de l'audit) :
- Pas de ``sympy.parse_expr`` (qui évalue du texte arbitraire) : on utilise
  ``fractions.Fraction``, exact, sans exécution de code et sans dépendance lourde
  (RAM de 512 Mo sur l'hébergement gratuit).
- Le signe ``-`` n'est un signe que s'il est isolé (« x = -3 »). Dans « 5-3 » ou
  « 12 - 4 = 8 », c'est un opérateur : on lit le DERNIER nombre (8).
- Si le nombre extrait est suivi d'une unité ou de ``%`` et ne correspond pas,
  la vérification est déclarée non concluante (conversion d'unité possible) au
  lieu de conclure à tort que l'élève a faux.
"""

import re
from fractions import Fraction
from typing import TypedDict

from app.core.i18n import DEFAULT_LANG, Lang

_PURE_NUMBER_RE = re.compile(r"^[-+]?\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?$")
# Nombre : signe optionnel (seulement s'il n'est pas collé à un chiffre/parenthèse
# qui précède), fraction « a/b » ou décimal.
_NUMBER_RE = re.compile(
    r"(?<![\w.,)])([-+−]?)(\d+(?:[.,]\d+)?)(?:\s*/\s*(\d+))?(?!\d)|(\d+(?:[.,]\d+)?)(?:\s*/\s*(\d+))?"
)
_UNIT_AFTER_RE = re.compile(r"^\s*(%|°|[a-zA-Zµ²³]{1,4}\b)")

_MAX_DIGITS = 18


class NumericCheck(TypedDict):
    """Résultat d'une vérification numérique."""

    checked: bool
    match: bool | None
    extracted: str | None
    note: str


def _to_fraction(sign: str, whole: str, denominator: str | None) -> Fraction | None:
    """Convertit les morceaux d'un nombre en ``Fraction`` exacte (ou ``None``)."""
    if len(whole) > _MAX_DIGITS or (denominator is not None and len(denominator) > _MAX_DIGITS):
        return None
    value = Fraction(whole.replace(",", "."))
    if denominator is not None:
        den = int(denominator)
        if den == 0:
            return None
        value = value / den
    if sign in ("-", "−"):
        value = -value
    return value


def parse_expected(expected: str) -> Fraction | None:
    """Lit la réponse attendue si elle est purement numérique.

    Args:
        expected: Valeur attendue (ex. ``"-3/4"``, ``"12,5"``, ``"x = 4"``).

    Returns:
        La valeur exacte, ou ``None`` si hors périmètre.
    """
    text = expected.strip()
    if "=" in text:
        text = text.split("=")[-1].strip()
    text = text.replace("−", "-").replace(" ", "")
    if not _PURE_NUMBER_RE.match(text):
        return None
    sign = "-" if text.startswith("-") else ""
    body = text.lstrip("+-")
    whole, _, denominator = body.partition("/")
    return _to_fraction(sign, whole, denominator or None)


def _is_unevaluated(before: str) -> bool:
    """Vrai si le nombre suit un opérateur binaire (« 5 - 3 » : calcul non terminé)."""
    stripped = before.rstrip()
    if len(stripped) < 2 or stripped[-1] not in "+-−*×÷/^x":
        return False
    return stripped[:-1].rstrip()[-1:].isdigit() or stripped[:-1].rstrip()[-1:] == ")"


def extract_last_number(student_text: str) -> tuple[Fraction, str, str, bool] | None:
    """Extrait le DERNIER nombre de la réponse de l'élève.

    Args:
        student_text: Texte libre de l'élève.

    Returns:
        ``(valeur, texte_du_nombre, reste_après, calcul_non_terminé)`` ou ``None``.
    """
    last: tuple[Fraction, str, str, bool] | None = None
    for m in _NUMBER_RE.finditer(student_text or ""):
        if m.group(2) is not None:
            sign, whole, den = m.group(1), m.group(2), m.group(3)
        else:
            sign, whole, den = "", m.group(4), m.group(5)
        value = _to_fraction(sign, whole, den)
        if value is not None:
            unevaluated = not sign and _is_unevaluated(student_text[: m.start()])
            last = (value, m.group(0).strip(), student_text[m.end() :], unevaluated)
    return last


def _t(lang: Lang, french: str, english: str) -> str:
    return english if lang == "en" else french


def verify_numeric_answer(expected: str, student_text: str, lang: Lang = DEFAULT_LANG) -> NumericCheck:
    """Compare la réponse numérique attendue au dernier nombre de l'élève.

    Ne lève jamais d'exception.

    Args:
        expected: Réponse numérique attendue (peut être vide).
        student_text: Réponse libre de l'élève.
        lang: Langue de la note explicative.

    Returns:
        Un dictionnaire ``{checked, match, extracted, note}``.
    """
    if not expected or not str(expected).strip():
        return {"checked": False, "match": None, "extracted": None, "note": ""}

    expected_value = parse_expected(str(expected))
    if expected_value is None:
        return {
            "checked": False,
            "match": None,
            "extracted": None,
            "note": _t(
                lang,
                "Vérification automatique non applicable (réponse attendue non numérique).",
                "Automatic check not applicable (the expected answer is not numeric).",
            ),
        }

    found = extract_last_number(student_text)
    if found is None:
        return {
            "checked": False,
            "match": None,
            "extracted": None,
            "note": _t(
                lang,
                "Vérification automatique non tentée (aucun nombre identifiable dans la réponse).",
                "Automatic check not attempted (no identifiable number in the answer).",
            ),
        }

    value, shown, rest, unevaluated = found
    is_match = value == expected_value
    if not is_match and unevaluated:
        return {
            "checked": False,
            "match": None,
            "extracted": shown,
            "note": _t(
                lang,
                "Vérification automatique non concluante (le calcul semble inachevé).",
                "Automatic check inconclusive (the calculation seems unfinished).",
            ),
        }
    if not is_match and _UNIT_AFTER_RE.match(rest):
        return {
            "checked": False,
            "match": None,
            "extracted": shown,
            "note": _t(
                lang,
                f"Vérification automatique non concluante sur « {shown} » (unité ou conversion possible).",
                f"Automatic check inconclusive on “{shown}” (possible unit or conversion).",
            ),
        }

    if lang == "en":
        verdict_en = "exactly matches" if is_match else "does NOT match"
        note = f"Automatic check: the numeric result extracted “{shown}” {verdict_en} the expected answer “{expected}”."
    else:
        verdict = "correspond exactement" if is_match else "NE correspond PAS"
        note = (
            f"Vérification automatique : le résultat numérique extrait « {shown} » "
            f"{verdict} à la réponse attendue « {expected} »."
        )
    return {"checked": True, "match": is_match, "extracted": shown, "note": note}
