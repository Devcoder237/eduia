"""Thèmes : normalisation des variantes et graphe de prérequis.

Les thèmes saisis librement ou générés par le modèle (« Les fractions », « fraction »,
« fractoins ») créaient autant de concepts distincts dans le profil, ce qui dispersait la
maîtrise. ``resolve_topic`` les rattache à une clé DÉJÀ stockée : les clés existantes ne
changent jamais.

Le graphe ``PREREQUISITES`` n'est qu'un POINT DE DÉPART (quelques exemples cohérents avec les
thèmes proposés par l'interface) : il doit être validé et complété par un enseignant du
programme camerounais avant d'être présenté comme une donnée pédagogique fiable.
"""

import difflib
import re
from collections.abc import Iterable

from app.services.rag_service import normalize_text

_ARTICLES = re.compile(r"^(?:les|le|la|l'|un|une|des|du|de la|de l'|d')\s*")
_FUZZY_CUTOFF = 0.88


def canonical_topic(topic: str) -> str:
    """Forme normalisée d'un thème (minuscules, sans accents, sans article, espaces réduits)."""
    text = normalize_text(topic).replace("’", "'").strip()
    text = " ".join(text.split())
    stripped = _ARTICLES.sub("", text, count=1).strip()
    return stripped or text


def resolve_topic(existing: Iterable[str], topic: str) -> str:
    """Rattache ``topic`` à une clé existante équivalente ; sinon renvoie ``topic`` nettoyé.

    Args:
        existing: Clés de thèmes déjà présentes dans le profil.
        topic: Thème reçu (peut être une variante ou contenir une faute de frappe).

    Returns:
        La clé existante correspondante (identique, variante normalisée ou très proche), ou le
        thème d'origine (espaces superflus retirés).
    """
    cleaned = " ".join(topic.split())
    keys = list(existing)
    if cleaned in keys:
        return cleaned
    wanted = canonical_topic(cleaned)
    by_canonical = {canonical_topic(k): k for k in keys}
    if wanted in by_canonical:
        return by_canonical[wanted]
    close = difflib.get_close_matches(wanted, list(by_canonical), n=1, cutoff=_FUZZY_CUTOFF)
    return by_canonical[close[0]] if close else cleaned


# matière -> {thème (forme canonique) : [prérequis (libellés d'interface)]}
_RAW_PREREQUISITES: dict[str, dict[str, list[str]]] = {
    "mathematiques": {
        "Équations 1er degré": ["Fractions & décimaux"],
        "Équations 2nd degré": ["Équations 1er degré"],
        "Proportionnalité": ["Fractions & décimaux"],
        "Probabilités": ["Fractions & décimaux"],
        "Trigonométrie": ["Théorème de Pythagore"],
        "Intégrales avancées": ["Dérivées"],
        "Équations différentielles": ["Intégrales avancées"],
    },
    "physique": {
        "Circuits électriques (Kirchhoff)": ["Électricité simple (U=RI)"],
        "Mécanique newtonienne": ["Les forces", "Vitesse et mouvement"],
        "Mécanique analytique": ["Mécanique newtonienne"],
    },
    "chimie": {
        "Acide-base (pH, pKa)": ["Mélanges et solutions"],
        "Oxydoréduction": ["Atomes et molécules"],
        "Chimie organique": ["Atomes et molécules"],
    },
    "biologie": {
        "ADN et chromosomes": ["La cellule"],
        "Génétique moléculaire": ["ADN et chromosomes"],
    },
}

PREREQUISITES: dict[str, dict[str, list[str]]] = {
    subject: {canonical_topic(concept): prereqs for concept, prereqs in graph.items()}
    for subject, graph in _RAW_PREREQUISITES.items()
}


def weak_prerequisites(subject: str, concept: str, effective: dict[str, float]) -> list[str]:
    """Prérequis du ``concept`` déjà travaillés mais MOINS bien maîtrisés que lui.

    Un prérequis jamais pratiqué n'est pas accusé (on ignore son niveau) ; seul un prérequis
    mesuré plus faible que le concept échoué justifie de revenir en arrière.

    Args:
        subject: Matière.
        concept: Concept échoué.
        effective: Maîtrise effective de la matière ``{concept: valeur}``.

    Returns:
        Libellés des prérequis faibles, du plus faible au moins faible.
    """
    prereqs = PREREQUISITES.get(subject, {}).get(canonical_topic(concept), [])
    own = effective.get(resolve_topic(effective, concept))
    if own is None:
        return []
    weak: list[tuple[float, str]] = []
    for label in prereqs:
        key = resolve_topic(effective, label)
        if key in effective and effective[key] < own:
            weak.append((effective[key], label))
    return [label for _, label in sorted(weak)]
