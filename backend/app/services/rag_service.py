"""RAG léger : sections pertinentes des fichiers ``knowledge_base/*.md``.

Pas de base vectorielle (mémoire limitée en gratuit) : classement des sections par BM25
(mots rares valorisés, longueur normalisée, titre compté double). Les fichiers sont mis en cache en mémoire.
"""

import math
import re
import unicodedata
from pathlib import Path

from app.core.logging import get_logger

log = get_logger(__name__)

KB_PATH = Path(__file__).resolve().parent.parent.parent / "knowledge_base"

SUBJECT_FILES: dict[str, list[str]] = {
    "mathematiques": ["programmes/MATHEMATIQUES.md", "examens/SUJETS_BEPC_BAC.md"],
    "physique": ["programmes/SCIENCES.md", "examens/SUJETS_BEPC_BAC.md"],
    "chimie": ["programmes/SCIENCES.md", "examens/SUJETS_BEPC_BAC.md"],
    "biologie": ["programmes/SCIENCES.md", "examens/SUJETS_BEPC_BAC.md"],
    "francais": ["programmes/LANGUES.md", "examens/SUJETS_BEPC_BAC.md"],
    "anglais": ["programmes/LANGUES.md", "examens/SUJETS_BEPC_BAC.md"],
    "histoire": ["programmes/HISTOIRE_GEO_INFO.md", "examens/SUJETS_BEPC_BAC.md"],
    "geographie": ["programmes/HISTOIRE_GEO_INFO.md"],
    "informatique": ["programmes/HISTOIRE_GEO_INFO.md"],
}

_LEVEL_LABELS = {"primaire": "Primaire", "college": "2nd cycle", "lycee": "Lycée", "universite": "Université"}
_STOP_WORDS = frozenset(
    {
        "le",
        "la",
        "les",
        "de",
        "du",
        "des",
        "un",
        "une",
        "et",
        "en",
        "est",
        "que",
        "qui",
        "dans",
        "je",
        "tu",
        "il",
        "nous",
        "vous",
        "comment",
        "quoi",
        "quel",
        "quelle",
        "pour",
        "avec",
        "sur",
        "par",
    }
)

_file_cache: dict[str, str] = {}


def _load_md_file(relative_path: str) -> str:
    """Charge un fichier .md de la base de connaissances (avec cache)."""
    cached = _file_cache.get(relative_path)
    if cached is not None:
        return cached
    full_path = (KB_PATH / relative_path).resolve()
    if KB_PATH not in full_path.parents or not full_path.is_file():
        return ""
    content = full_path.read_text(encoding="utf-8")
    _file_cache[relative_path] = content
    return content


def normalize_text(text: str) -> str:
    """Minuscules sans accents : « dérivée » et « derivee » se recoupent (clavier mobile)."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


_K1 = 1.5  # saturation de la fréquence d'un mot
_B = 0.75  # normalisation par la longueur de la section
_ACRONYM = re.compile(r"^(?=.*[A-Z])[A-Za-z0-9]{2,4}$")  # pH, ADN, DNA, CO2 : courts mais porteurs de sens


def _stem(token: str) -> str:
    """Retire le pluriel le plus courant (« dérivées » / « dérivée » se recoupent)."""
    return token[:-1] if len(token) > 4 and token[-1] in "sx" else token


def _tokens(text: str) -> list[str]:
    return [_stem(t) for t in re.findall(r"[a-z0-9]+", normalize_text(text)) if t not in _STOP_WORDS]


def _query_terms(query: str) -> set[str]:
    """Mots utiles de la requête : mots de plus de 3 lettres, et sigles courts (pH, ADN)."""
    terms: set[str] = set()
    for raw in re.findall(r"[A-Za-z0-9\u00C0-\u017F]+", query):
        normalized = normalize_text(raw)
        if normalized in _STOP_WORDS:
            continue
        if len(normalized) > 3 or (_ACRONYM.match(raw) and len(normalized) >= 2):
            terms.add(_stem(normalized))
    return terms


def bm25_rank(sections: list[str], query: str) -> list[tuple[float, str]]:
    """Classe les sections par pertinence BM25 (les sections sans aucun mot commun sont écartées).

    Les mots rares pèsent plus que les mots courants (IDF), une section longue n'est pas
    avantagée (normalisation par la longueur), et un mot présent dans le TITRE compte double.
    """
    terms = _query_terms(query)
    if not terms or not sections:
        return []
    docs: list[list[str]] = []
    for section in sections:
        lines = section.strip().split("\n", 1)
        title_tokens = _tokens(lines[0]) if lines and lines[0].lstrip().startswith("#") else []
        docs.append(_tokens(section) + title_tokens)  # le titre compte deux fois
    n = len(docs)
    avg_len = (sum(len(d) for d in docs) / n) or 1.0
    doc_freq = {t: sum(1 for d in docs if t in d) for t in terms}
    ranked: list[tuple[float, str]] = []
    for section, tokens in zip(sections, docs, strict=True):
        counts: dict[str, int] = {}
        for tok in tokens:
            if tok in terms:
                counts[tok] = counts.get(tok, 0) + 1
        score = 0.0
        for term, tf in counts.items():
            idf = math.log(1.0 + (n - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            score += idf * tf * (_K1 + 1.0) / (tf + _K1 * (1.0 - _B + _B * len(tokens) / avg_len))
        if score > 0:
            ranked.append((score, section.strip()))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked


def extract_relevant_sections(md_content: str, query: str, max_chars: int = 2000) -> str:
    """Sélectionne les sections (titres ``#``) les plus pertinentes pour la requête (BM25).

    Args:
        md_content: Contenu Markdown.
        query: Texte de recherche.
        max_chars: Taille maximale du résultat.

    Returns:
        Les meilleures sections concaténées ; une section plus longue que la limite est
        TRONQUÉE (au lieu d'être perdue) ; chaîne vide si rien ne correspond (on n'injecte plus
        le début du fichier, sans rapport avec la question).
    """
    if not md_content:
        return ""
    sections = re.split(r"\n(?=#{1,3} )", md_content)
    parts: list[str] = []
    total = 0
    for _, section in bm25_rank(sections, query):
        room = max_chars - total
        if len(section) <= room:
            parts.append(section)
            total += len(section)
        elif not parts:
            parts.append(section[:max_chars].rstrip())  # meilleure section trop longue : on la coupe
            break
    return "\n\n---\n\n".join(parts)


class RAGService:
    """Fournit au tuteur des extraits du programme officiel camerounais."""

    def __init__(self) -> None:
        if KB_PATH.exists():
            log.info("rag_ready", files=len(list(KB_PATH.rglob("*.md"))))
        else:
            log.warning("rag_knowledge_base_missing")

    async def retrieve(self, query: str, subject: str, level: str, top_k: int = 3) -> str | None:
        """Récupère les passages pertinents pour enrichir une réponse.

        Args:
            query: Question de l'élève.
            subject: Matière.
            level: Niveau scolaire.
            top_k: Nombre maximal de blocs retournés.

        Returns:
            Le contexte, ou ``None`` si rien de pertinent.
        """
        collected: list[str] = []
        rules = _load_md_file("regles/REGLES_TUTEUR.md")
        label = _LEVEL_LABELS.get(level.lower(), "")
        if rules and label:
            section = extract_relevant_sections(rules, label, max_chars=500)
            if section:
                collected.append(f"**Règles pédagogiques pour le niveau {label} :**\n{section}")

        for file_path in SUBJECT_FILES.get(subject.lower().strip(), []):
            content = _load_md_file(file_path)
            section = extract_relevant_sections(content, f"{query} {level} {subject}", max_chars=1500)
            if section:
                title = Path(file_path).stem.replace("_", " ").title()
                collected.append(f"**Source : {title}**\n{section}")

        if not collected:
            return None
        return "\n\n═══════════════\n\n".join(collected[: max(1, top_k)])


rag_service = RAGService()
