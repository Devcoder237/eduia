"""Langue de la requête (fr/en) : lecture de l'en-tête, consignes de langue pour l'IA, messages.

Principe (bilinguisme de bout en bout) :

- le frontend envoie ``Accept-Language: fr|en`` sur CHAQUE requête (flux SSE compris) ;
- ``get_lang`` en déduit ``"fr"`` (défaut, comportement historique) ou ``"en"`` ;
- les services de génération reçoivent ``lang`` et ajoutent une règle de langue explicite
  au prompt (``language_rule``) : les consignes restent écrites une seule fois, en français ;
- les messages fixes du serveur (erreurs HTTP) restent écrits en français dans le code et sont
  traduits au moment de la réponse par ``translate_detail`` (table ``_EN_EXACT`` + motifs).
  Un test vérifie que chaque message ``detail="..."`` du code possède sa traduction ;
- les identifiants de données (thèmes/concepts) restent en français : l'historique de maîtrise
  d'un élève ne doit pas se scinder selon la langue d'affichage. Seuls les LIBELLÉS sont traduits.
"""

import re
from collections.abc import Callable
from typing import Literal

from fastapi import Request

Lang = Literal["fr", "en"]
DEFAULT_LANG: Lang = "fr"
SUPPORTED: tuple[Lang, ...] = ("fr", "en")

_LANG_NAME: dict[Lang, str] = {"fr": "French", "en": "English"}


def parse_lang(header: str | None) -> Lang:
    """Extrait la langue d'un en-tête ``Accept-Language`` (``fr`` par défaut, valeur inconnue ignorée).

    Args:
        header: Valeur brute de l'en-tête (ex. ``en-US,en;q=0.9``), ou ``None``.

    Returns:
        ``"en"`` ou ``"fr"``. On retient la première langue SUPPORTÉE par ordre de préférence ;
        une priorité nulle ou illisible (``q=abc``) écarte la langue.
    """
    if not header:
        return DEFAULT_LANG
    ranked: list[tuple[float, int, str]] = []
    for index, part in enumerate(header.split(",")):
        piece = part.strip()
        if not piece:
            continue
        tag, _, params = piece.partition(";")
        quality = 1.0
        match = re.search(r"q\s*=\s*([^;,\s]+)", params)
        if match:
            try:
                quality = float(match.group(1))
            except ValueError:
                quality = 0.0
        if quality <= 0:
            continue  # q=0 (ou q illisible) : langue « non acceptable », comme le prévoit la norme HTTP
        ranked.append((-quality, index, tag.strip().lower().split("-")[0]))
    for _, _, primary in sorted(ranked):
        if primary in SUPPORTED:
            return "en" if primary == "en" else "fr"
    return DEFAULT_LANG


def lang_of(request: Request) -> Lang:
    """Langue de la requête HTTP."""
    return parse_lang(request.headers.get("accept-language"))


async def get_lang(request: Request) -> Lang:
    """Dépendance FastAPI : langue demandée par le client."""
    return lang_of(request)


def language_rule(lang: Lang, subject: str | None = None) -> str:
    """Règle de langue à ajouter à la FIN d'un prompt de génération.

    En français : comportement historique. En anglais : la règle prime sur toute consigne
    contraire des instructions (rédigées en français) et précise le cas des matières de langues.

    Args:
        lang: Langue de sortie voulue.
        subject: Matière (``anglais`` / ``francais`` ont un traitement particulier).

    Returns:
        Un bloc de texte prêt à être concaténé au prompt.
    """
    if lang == "fr":
        return (
            "\n## REGLE DE LANGUE\n"
            "Redige TOUT texte destine a l'eleve en francais (matiere anglais : explications en "
            "francais, exemples en anglais).\n"
        )
    special = ""
    if subject == "anglais":
        special = (
            " Subject = English: teach English IN English (immersion); full-sentence examples; "
            "simple vocabulary for lower levels.\n"
        )
    elif subject == "francais":
        special = " Subject = French: explain in English and quote the French examples/rules in French.\n"
    return (
        "\n## LANGUAGE RULE (HIGHEST PRIORITY)\n"
        "The instructions above are written in French, but you MUST write EVERY piece of text "
        "meant for the student in ENGLISH: explanations, questions, answer choices, hints, "
        "solutions, rubric criteria, feedback, study-plan labels. This rule overrides any "
        "instruction above that says to answer in French (including 'explique en francais'). "
        "Keep JSON keys EXACTLY as specified; only the values are in English. Do not mention "
        "this rule." + special
    )


def output_language_name(lang: Lang) -> str:
    """Nom anglais de la langue de sortie (utile aux journaux et aux tests)."""
    return _LANG_NAME[lang]


SUBJECT_NAMES: dict[Lang, dict[str, str]] = {
    "fr": {
        "mathematiques": "Mathématiques",
        "physique": "Physique",
        "chimie": "Chimie",
        "biologie": "Biologie",
        "francais": "Français",
        "anglais": "Anglais",
        "histoire": "Histoire-Géo",
        "informatique": "Informatique",
    },
    "en": {
        "mathematiques": "Mathematics",
        "physique": "Physics",
        "chimie": "Chemistry",
        "biologie": "Biology",
        "francais": "French",
        "anglais": "English",
        "histoire": "History & Geography",
        "informatique": "Computer science",
    },
}


def subject_name(subject: str, lang: Lang) -> str:
    """Nom d'affichage d'une matière (identifiant français inconnu : renvoyé tel quel)."""
    return SUBJECT_NAMES[lang].get(subject, subject)


_BADGES_EN: dict[str, tuple[str, str]] = {
    "first_session": ("First step", "First session completed"),
    "questions_100": ("Endlessly curious", "100 questions asked"),
    "streak_7": ("Perfect week", "7 days in a row"),
    "streak_30": ("Month of discipline", "30 days in a row"),
    "math_expert": ("Maths expert", "Score ≥ 90% in mathematics"),
    "polyglot": ("Polyglot", "Score ≥ 70% in French and English"),
    "perfect_score": ("Perfect score", "100% on an exercise"),
}


def localize_badge(code: str, name: str, description: str, lang: Lang) -> tuple[str, str]:
    """Nom et description d'un badge dans la langue demandée (texte d'origine si inconnu)."""
    if lang == "en" and code in _BADGES_EN:
        return _BADGES_EN[code]
    return name, description


# --- Messages d'erreur : français (source) -> anglais ------------------------------------

_EN_EXACT: dict[str, str] = {
    "Cette demande est déjà en cours de traitement.": "This request is already being processed.",
    "Le tuteur IA n'a pas réussi à créer l'exercice. Réessaie.": "The AI tutor couldn't create the exercise. Please try again.",
    "Le tuteur IA n'a pas réussi à créer la question. Réessaie.": "The AI tutor couldn't create the question. Please try again.",
    "Question introuvable.": "Question not found.",
    "Cet email est déjà utilisé.": "This email is already in use.",
    "Ce nom d'utilisateur est déjà pris.": "This username is already taken.",
    "Cet email ou ce nom d'utilisateur existe déjà.": "This email or username already exists.",
    "Email ou mot de passe incorrect.": "Incorrect email or password.",
    "Ce compte est désactivé.": "This account is disabled.",
    "Ta session a expiré. Reconnecte-toi, s'il te plaît.": "Your session has expired. Please sign in again.",
    "Le mot de passe actuel est incorrect.": "The current password is incorrect.",
    "Le mot de passe est incorrect.": "The password is incorrect.",
    "Ce lien est invalide ou a expiré. Demande un nouveau lien.": "This link is invalid or has expired. Please request a new one.",
    "Si un compte existe avec cet e-mail, un lien de réinitialisation vient d'être envoyé.": "If an account exists for this email, a reset link has just been sent.",
    "Mot de passe réinitialisé. Connecte-toi avec ton nouveau mot de passe.": "Password reset. Sign in with your new password.",
    "Exercice introuvable.": "Exercise not found.",
    "Session introuvable.": "Session not found.",
    "Format non supporté. Formats acceptés : PDF, Word (.docx), PowerPoint (.pptx).": "Unsupported format. Accepted formats: PDF, Word (.docx), PowerPoint (.pptx).",
    "Impossible de générer un code d'invitation unique, réessaie.": "Couldn't generate a unique invite code, please try again.",
    "Code d'invitation invalide ou classe inactive.": "Invalid invite code or inactive class.",
    "Tu ne fais pas partie de cette classe.": "You are not a member of this class.",
    "Classe introuvable.": "Class not found.",
    "Plan introuvable.": "Plan not found.",
    "La date cible doit être dans le futur.": "The target date must be in the future.",
    "Index de jour invalide.": "Invalid day index.",
    "Examen introuvable.": "Exam not found.",
    "Question d'examen introuvable.": "Exam question not found.",
    "Cet examen est déjà terminé.": "This exam is already finished.",
    "Connecte-toi pour continuer.": "Please sign in to continue.",
    "Accès réservé aux administrateurs.": "Access restricted to administrators.",
    "Accès réservé aux enseignants.": "Access restricted to teachers.",
    "Doucement, tu vas trop vite ! Attends un petit moment avant de réessayer.": "Slow down, you're going too fast! Wait a moment before trying again.",
    "Tu as atteint ta limite d'aujourd'hui pour le tuteur IA. Reviens demain, et pense à réviser avec tes cahiers en attendant ! 📚": "You've reached today's limit for the AI tutor. Come back tomorrow, and revise with your notebooks in the meantime! 📚",
    "Le tuteur IA n'est pas disponible pour le moment. Réessaie plus tard.": "The AI tutor is not available right now. Please try again later.",
    "Le tuteur IA est très sollicité en ce moment. Réessaie dans une minute.": "The AI tutor is very busy right now. Please try again in a minute.",
    "Le tuteur IA met trop de temps à répondre. Réessaie dans un instant.": "The AI tutor is taking too long to answer. Please try again in a moment.",
    "Le tuteur IA est momentanément indisponible.": "The AI tutor is temporarily unavailable.",
    "Le tuteur IA a rencontré un problème. Réessaie dans un instant.": "The AI tutor ran into a problem. Please try again in a moment.",
    "Le tuteur IA a produit une réponse inattendue. Réessaie dans un instant.": "The AI tutor produced an unexpected answer. Please try again in a moment.",
    "Impossible de lire ce fichier. Il est peut-être corrompu, protégé ou trop volumineux.": "Unable to read this file. It may be corrupted, protected or too large.",
    "Aucun texte exploitable trouvé (le document est peut-être une image scannée).": "No usable text found (the document may be a scanned image).",
    "Données invalides.": "Invalid data.",
    "Oups, une erreur est survenue de notre côté. Réessaie dans un instant.": "Oops, something went wrong on our side. Please try again in a moment.",
    "Le nom d'utilisateur ne peut contenir que lettres, chiffres, « _ », « . » et « - ».": "The username may only contain letters, digits, “_”, “.” and “-”.",
}

_EN_LABELS = {"Le mot de passe": "The password", "Le nouveau mot de passe": "The new password"}

# (motif français, fonction de traduction) pour les messages à valeurs variables.
_EN_PATTERNS: tuple[tuple[re.Pattern[str], Callable[[re.Match[str]], str]], ...] = (
    (
        re.compile(r"^Fichier trop volumineux \((\d+) Mo maximum\)\.$"),
        lambda m: f"File too large ({m[1]} MB maximum).",
    ),
    (
        re.compile(r"^La date cible est trop lointaine \((\d+) jours maximum\)\.$"),
        lambda m: f"The target date is too far away ({m[1]} days maximum).",
    ),
    (
        re.compile(r"^(Le mot de passe|Le nouveau mot de passe) est trop long \(72 octets maximum\)\.$"),
        lambda m: f"{_EN_LABELS[m[1]]} is too long (72 bytes maximum).",
    ),
    (
        re.compile(r"^(Le mot de passe|Le nouveau mot de passe) doit contenir au moins une majuscule\.$"),
        lambda m: f"{_EN_LABELS[m[1]]} must contain at least one uppercase letter.",
    ),
    (
        re.compile(r"^(Le mot de passe|Le nouveau mot de passe) doit contenir au moins un chiffre\.$"),
        lambda m: f"{_EN_LABELS[m[1]]} must contain at least one digit.",
    ),
)


def translate_detail(detail: str, lang: Lang) -> str:
    """Traduit un message d'erreur serveur ; renvoie le texte d'origine si inconnu ou si ``lang == "fr"``."""
    if lang == "fr":
        return detail
    known = _EN_EXACT.get(detail)
    if known is not None:
        return known
    for pattern, render in _EN_PATTERNS:
        match = pattern.match(detail)
        if match:
            return render(match)
    return detail


def known_french_messages() -> frozenset[str]:
    """Messages français ayant une traduction exacte (utilisé par le test de couverture)."""
    return frozenset(_EN_EXACT)
