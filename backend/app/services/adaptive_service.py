"""Apprentissage adaptatif : BKT (Bayesian Knowledge Tracing), oubli, recommandations.

Les dates sont UTC « aware » ; la série de jours (streak) est calculée sur le
jour *local* (UTC+1, Cameroun) pour ne pas casser une série à 23 h 30 locale.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.i18n import DEFAULT_LANG, Lang, subject_name
from app.core.timeutil import ensure_utc, to_local_date, utcnow
from app.models.models import LearnerProfile
from app.services.topics import resolve_topic, weak_prerequisites


class MasteryTracker:
    """Modèle BKT (Corbett & Anderson, 1995) : apprentissage, hasard, étourderie, a priori.

    Choix de modélisation (à justifier dans le mémoire) :

    - Les paramètres sont des valeurs usuelles de la littérature, NON calibrées sur des
      données camerounaises : calibrer par EM (ex. pyBKT, voir ``scripts/export_bkt_data.py``)
      dès que suffisamment de réponses réelles sont collectées.
    - Le HASARD dépend du type d'item : 25 % pour un QCM à 4 options (``ITEM_PARAMS``), très
      bas pour une réponse rédigée. Un QCM réussi est donc une preuve plus faible qu'un
      exercice réussi (avant : un même ``P_GUESS`` = 0,10 surestimait la maîtrise au QCM).
    - Chaque INDICE consommé, et une confiance déclarée « je devine », relèvent la
      probabilité de hasard : une réussite aidée prouve moins.
    - ``P_INIT`` : a priori de maîtrise d'un concept jamais vu (prudent : 0,3).
    - L'OUBLI n'est pas un paramètre du BKT classique : décroissance exponentielle appliquée
      à la lecture ET avant chaque mise à jour, avec une STABILITÉ propre à chaque concept
      (elle double à chaque réussite, comme en répétition espacée). Elle décroît vers
      l'a priori ``P_INIT`` et non vers 0 : un concept oublié n'est pas pire qu'un concept
      inconnu.
    - Le code importe directement cette classe dans les tests et simulations : aucune
      réimplémentation parallèle qui pourrait diverger.
    """

    P_INIT = 0.30
    P_LEARN = 0.20
    P_GUESS = 0.10
    P_SLIP = 0.08
    FORGETTING_TAU_DAYS = 30.0  # stabilité initiale d'un concept (jours)

    # (hasard, étourderie) par type d'item ; type inconnu : P_GUESS / P_SLIP.
    ITEM_PARAMS: dict[str, tuple[float, float]] = {"mcq": (0.25, 0.08), "open": (0.05, 0.10)}
    HINT_GUESS_BOOST = 0.15
    MAX_GUESS = 0.60
    MIN_STABILITY_DAYS = 3.0
    MAX_STABILITY_DAYS = 365.0

    @classmethod
    def update(
        cls,
        prior: float,
        correct: bool,
        item_type: str | None = None,
        hints_used: int = 0,
        confidence: int | None = None,
    ) -> float:
        """Met à jour la maîtrise d'un concept après une réponse.

        Args:
            prior: Maîtrise avant la réponse (0..1).
            correct: La réponse était-elle correcte ?
            item_type: ``"mcq"`` (QCM) ou ``"open"`` (réponse rédigée) ; ``None`` = défaut.
            hints_used: Indices consommés avant la réponse (relèvent le hasard).
            confidence: Confiance déclarée (1 = « je devine », 2, 3) ; la confiance 1 compte
                comme un indice de plus. Les confiances 2 et 3 ne modifient pas le modèle.

        Returns:
            La nouvelle maîtrise, bornée à [0, 1], arrondie à 4 décimales.
        """
        guess, slip = cls.ITEM_PARAMS.get(item_type or "", (cls.P_GUESS, cls.P_SLIP))
        boosts = max(0, hints_used) + (1 if confidence == 1 else 0)
        guess = min(cls.MAX_GUESS, guess + cls.HINT_GUESS_BOOST * boosts)
        if correct:
            p_given_learned = 1.0 - slip
            p_given_unlearned = guess
        else:
            p_given_learned = slip
            p_given_unlearned = 1.0 - guess
        numerator = p_given_learned * prior
        denominator = numerator + p_given_unlearned * (1.0 - prior)
        posterior = numerator / denominator if denominator > 0 else prior
        updated = posterior + (1.0 - posterior) * cls.P_LEARN
        return round(max(0.0, min(1.0, updated)), 4)

    @classmethod
    def retention(cls, days_since: float, stability: float | None = None) -> float:
        """Probabilité de se souvenir après ``days_since`` jours : ``exp(-t / stabilité)``."""
        stab = stability if stability and stability > 0 else cls.FORGETTING_TAU_DAYS
        return math.exp(-max(0.0, days_since) / stab)

    @classmethod
    def apply_forgetting(
        cls, mastery: float, days_since: float, stability: float | None = None, floor: float = 0.0
    ) -> float:
        """Applique la courbe d'oubli : la maîtrise décroît vers ``floor`` (jamais en dessous).

        Args:
            mastery: Maîtrise avant oubli.
            days_since: Jours écoulés depuis la dernière pratique (négatif = 0).
            stability: Stabilité du concept en jours (défaut ``FORGETTING_TAU_DAYS``).
            floor: Plancher de l'oubli (0 = oubli total ; ``P_INIT`` = retour à l'a priori).
        """
        if mastery <= floor:
            return round(mastery, 4)
        return round(floor + (mastery - floor) * cls.retention(days_since, stability), 4)

    @classmethod
    def next_stability(cls, stability: float | None, correct: bool, hints_used: int = 0) -> float:
        """Nouvelle stabilité : ×2 après réussite, ×1,2 si aidée, ×0,5 après échec."""
        current = stability if stability and stability > 0 else cls.FORGETTING_TAU_DAYS
        factor = 0.5 if not correct else (1.2 if hints_used > 0 else 2.0)
        return round(max(cls.MIN_STABILITY_DAYS, min(cls.MAX_STABILITY_DAYS, current * factor)), 2)


@dataclass(frozen=True)
class BadgeRule:
    """Définition d'un badge et de sa condition d'obtention."""

    code: str
    name: str
    icon: str
    description: str
    rarity: str
    condition: Callable[[LearnerProfile], bool] | None


def _score(profile: LearnerProfile, subject: str) -> float:
    scores: dict[str, Any] = profile.subject_scores or {}
    return float(scores.get(subject, 0) or 0)


def _attempts(profile: LearnerProfile, subject: str) -> tuple[int, int]:
    """(nombre de concepts suivis, nombre total de tentatives) pour une matière."""
    stats: dict[str, Any] = (getattr(profile, "concept_stats", None) or {}).get(subject, {})
    return len(stats), sum(int(v.get("attempts", 0)) for v in stats.values())


def _is_math_expert(profile: LearnerProfile) -> bool:
    """Score ≥ 90 % sur au moins 3 concepts et 10 tentatives (un seul exercice ne suffit plus)."""
    concepts, attempts = _attempts(profile, "mathematiques")
    return _score(profile, "mathematiques") >= 0.90 and concepts >= 3 and attempts >= 10


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return ensure_utc(datetime.fromisoformat(value))
    except ValueError:
        return None


BADGE_RULES: tuple[BadgeRule, ...] = (
    BadgeRule(
        "first_session",
        "Premier pas",
        "🚀",
        "Première session complétée",
        "common",
        lambda p: (p.total_sessions or 0) >= 1,
    ),
    BadgeRule(
        "questions_100",
        "Curieux insatiable",
        "💡",
        "100 questions posées",
        "common",
        lambda p: (p.total_questions or 0) >= 100,
    ),
    BadgeRule(
        "streak_7",
        "Semaine parfaite",
        "🔥",
        "7 jours consécutifs",
        "rare",
        lambda p: (p.streak_days or 0) >= 7,
    ),
    BadgeRule(
        "streak_30",
        "Mois de discipline",
        "🏆",
        "30 jours consécutifs",
        "epic",
        lambda p: (p.streak_days or 0) >= 30,
    ),
    BadgeRule(
        "math_expert",
        "Expert Maths",
        "⭐",
        "Score ≥ 90% en mathématiques (3 concepts, 10 tentatives)",
        "epic",
        _is_math_expert,
    ),
    BadgeRule(
        "polyglot",
        "Polyglotte",
        "🌍",
        "Score ≥ 70% FR + EN",
        "rare",
        lambda p: _score(p, "francais") >= 0.70 and _score(p, "anglais") >= 0.70,
    ),
    # Événement ponctuel (score exact d'un exercice) : géré via ``context``.
    BadgeRule("perfect_score", "Score parfait", "💎", "100% à un exercice", "legendary", None),
)


class AdaptiveLearningService:
    """Mise à jour du profil, maîtrise effective, recommandations, badges."""

    def update_profile_after_interaction(
        self,
        profile: LearnerProfile,
        subject: str,
        topic: str,
        is_correct: bool | None = None,
        score: float | None = None,
        new_session: bool = False,
        item_type: str | None = None,
        hints_used: int = 0,
        confidence: int | None = None,
    ) -> LearnerProfile:
        """Met à jour le profil après une interaction.

        Args:
            profile: Profil à modifier.
            subject: Matière (valeur textuelle).
            topic: Concept travaillé.
            is_correct: Réponse correcte (met à jour la maîtrise BKT du concept).
            score: Score global 0..1 (lissage exponentiel, si ``is_correct`` est None).
            new_session: ``True`` UNE fois par session logique terminée (fin de
                quiz/examen/exercice), jamais à chaque question.
            item_type: ``"mcq"`` ou ``"open"`` (réglage du hasard du BKT).
            hints_used: Indices consommés avant la réponse.
            confidence: Confiance déclarée au QCM (1 à 3), ou ``None``.

        Returns:
            Le profil modifié.
        """
        now = utcnow()
        profile.total_questions = (profile.total_questions or 0) + 1
        if new_session:
            profile.total_sessions = (profile.total_sessions or 0) + 1

        if is_correct is not None:
            mastery = dict(profile.concept_mastery or {})
            subject_mastery = dict(mastery.get(subject, {}))
            topic = resolve_topic(subject_mastery.keys(), topic)  # « Les fractions » → « fractions »
            stats = dict(getattr(profile, "concept_stats", None) or {})
            subject_stats = dict(stats.get(subject, {}))
            concept_stat = dict(subject_stats.get(topic, {}))
            stability = float(concept_stat.get("stability") or MasteryTracker.FORGETTING_TAU_DAYS)

            # L'oubli est appliqué AVANT la mise à jour : on met à jour ce que l'élève sait vraiment.
            prior = float(subject_mastery.get(topic, MasteryTracker.P_INIT))
            previous = _parse_date(((profile.concept_last_practiced or {}).get(subject, {})).get(topic))
            if previous is not None:
                days = max(0.0, (now - previous).total_seconds() / 86400.0)
                prior = MasteryTracker.apply_forgetting(prior, days, stability, floor=MasteryTracker.P_INIT)
            subject_mastery[topic] = MasteryTracker.update(
                prior, is_correct, item_type, hints_used, confidence
            )
            mastery[subject] = subject_mastery
            profile.concept_mastery = mastery

            concept_stat["attempts"] = int(concept_stat.get("attempts", 0)) + 1
            concept_stat["correct"] = int(concept_stat.get("correct", 0)) + (1 if is_correct else 0)
            concept_stat["stability"] = MasteryTracker.next_stability(stability, is_correct, hints_used)
            subject_stats[topic] = concept_stat
            stats[subject] = subject_stats
            profile.concept_stats = stats

            # Score de la matière : moyenne pondérée par le nombre de tentatives (plafonné à 5),
            # pour qu'un concept essayé une seule fois ne pèse pas autant qu'un concept travaillé.
            weights = {
                c: min(5, max(1, int(subject_stats.get(c, {}).get("attempts", 1)))) for c in subject_mastery
            }
            total_weight = sum(weights.values())
            subject_scores = dict(profile.subject_scores or {})
            subject_scores[subject] = round(
                sum(float(v) * weights[c] for c, v in subject_mastery.items()) / total_weight, 4
            )
            profile.subject_scores = subject_scores

            last_practiced = dict(profile.concept_last_practiced or {})
            subject_dates = dict(last_practiced.get(subject, {}))
            subject_dates[topic] = now.isoformat()
            last_practiced[subject] = subject_dates
            profile.concept_last_practiced = last_practiced
        elif score is not None:
            subject_scores = dict(profile.subject_scores or {})
            current = float(subject_scores.get(subject, 0.5))
            subject_scores[subject] = round(0.2 * score + 0.8 * current, 4)
            profile.subject_scores = subject_scores

        last_activity = ensure_utc(profile.last_activity)
        if last_activity is None:
            profile.streak_days = 1
        else:
            gap = (to_local_date(now) - to_local_date(last_activity)).days
            if gap == 1:
                profile.streak_days = (profile.streak_days or 0) + 1
            elif gap > 1 or not profile.streak_days:
                profile.streak_days = 1
        profile.last_activity = now
        profile.updated_at = now
        return profile

    def get_effective_mastery(self, profile: LearnerProfile) -> dict[str, dict[str, float]]:
        """Retourne la maîtrise par concept, oubli appliqué (stabilité du concept, plancher ``P_INIT``)."""
        raw_mastery: dict[str, dict[str, float]] = profile.concept_mastery or {}
        last_practiced: dict[str, dict[str, str]] = profile.concept_last_practiced or {}
        stats: dict[str, Any] = getattr(profile, "concept_stats", None) or {}
        now = utcnow()
        effective: dict[str, dict[str, float]] = {}
        for subject, concepts in raw_mastery.items():
            effective[subject] = {}
            subject_dates = last_practiced.get(subject, {})
            for concept, value in concepts.items():
                parsed = _parse_date(subject_dates.get(concept))
                days_since = max(0.0, (now - parsed).total_seconds() / 86400.0) if parsed else 0.0
                stability = stats.get(subject, {}).get(concept, {}).get("stability")
                effective[subject][concept] = MasteryTracker.apply_forgetting(
                    float(value), days_since, stability, floor=MasteryTracker.P_INIT
                )
        return effective

    def concept_level(self, profile: LearnerProfile, subject: str, concept: str) -> float:
        """Maîtrise effective du concept visé ; à défaut, moyenne de la matière ; à défaut, 0,5."""
        effective = self.get_effective_mastery(profile).get(subject, {})
        if concept in effective:
            return effective[concept]
        if effective:
            return sum(effective.values()) / len(effective)
        return 0.5

    def get_due_reviews(
        self, profile: LearnerProfile, threshold: float = 0.70, min_mastery: float = 0.50
    ) -> list[dict[str, Any]]:
        """Concepts APPRIS (maîtrise ≥ ``min_mastery``) dont la rétention prévue passe sous ``threshold``.

        C'est la répétition espacée : on révise juste avant d'oublier, pas après. Trié du plus
        urgent (rétention la plus basse) au moins urgent.
        """
        due: list[dict[str, Any]] = []
        last_practiced: dict[str, dict[str, str]] = profile.concept_last_practiced or {}
        stats: dict[str, Any] = getattr(profile, "concept_stats", None) or {}
        now = utcnow()
        for subject, concepts in (profile.concept_mastery or {}).items():
            for concept, value in concepts.items():
                if float(value) < min_mastery:
                    continue
                parsed = _parse_date(last_practiced.get(subject, {}).get(concept))
                if parsed is None:
                    continue
                days = max(0.0, (now - parsed).total_seconds() / 86400.0)
                stability = stats.get(subject, {}).get(concept, {}).get("stability")
                retention = MasteryTracker.retention(days, stability)
                if retention < threshold:
                    due.append(
                        {
                            "subject": subject,
                            "concept": concept,
                            "mastery": float(value),
                            "retention": round(retention, 3),
                        }
                    )
        due.sort(key=lambda d: float(d["retention"]))
        return due

    def get_recommendations(
        self, profile: LearnerProfile, n: int = 5, lang: Lang = DEFAULT_LANG
    ) -> list[dict[str, Any]]:
        """Construit les recommandations (concepts faibles puis matières moyennes).

        Args:
            profile: Profil de l'élève.
            n: Nombre maximal de recommandations.
            lang: Langue des textes ``reason`` et ``action``.
        """
        recommendations: list[dict[str, Any]] = []
        mastery = self.get_effective_mastery(profile)
        scores: dict[str, float] = profile.subject_scores or {}
        for subject, concepts in mastery.items():
            for concept, value in concepts.items():
                if value < 0.50:
                    weak = weak_prerequisites(subject, concept, concepts)
                    if weak:
                        chain = ", ".join(weak) + (
                            f", then {concept}" if lang == "en" else f", puis {concept}"
                        )
                        action = f"Exercises on {chain}" if lang == "en" else f"Exercices sur {chain}"
                    else:
                        action = f"Exercises on {concept}" if lang == "en" else f"Exercices sur {concept}"
                    recommendations.append(
                        {
                            "priority": "high",
                            "subject": subject,
                            "concept": concept,
                            "score": value,
                            "reason": (
                                f"Mastery at {int(value * 100)}% — urgent review"
                                if lang == "en"
                                else f"Maîtrise à {int(value * 100)}% — révision urgente"
                            ),
                            "action": action,
                        }
                    )
        # Répétition espacée : concepts appris mais bientôt oubliés (on révise avant d'oublier).
        weak_keys = {(r["subject"], r["concept"]) for r in recommendations}
        for due in self.get_due_reviews(profile):
            if (due["subject"], due["concept"]) in weak_keys:
                continue
            pct = int(float(due["retention"]) * 100)
            recommendations.append(
                {
                    "priority": "medium",
                    "subject": due["subject"],
                    "concept": due["concept"],
                    "score": mastery.get(due["subject"], {}).get(due["concept"], float(due["mastery"])),
                    "reason": (
                        f"To review (spaced repetition) — estimated retention {pct}%"
                        if lang == "en"
                        else f"À revoir (répétition espacée) — rétention estimée {pct} %"
                    ),
                    "action": f"Quick review of {due['concept']}"
                    if lang == "en"
                    else f"Révision rapide de {due['concept']}",
                }
            )
        for subject, score in scores.items():
            if 0.50 <= score < 0.70:
                recommendations.append(
                    {
                        "priority": "medium",
                        "subject": subject,
                        "concept": None,
                        "score": score,
                        "reason": (
                            f"Overall score {int(score * 100)}% — room to improve"
                            if lang == "en"
                            else f"Score global {int(score * 100)}% — peut progresser"
                        ),
                        "action": (
                            f"Strengthen {subject_name(subject, 'en')}"
                            if lang == "en"
                            else f"Renforcement en {subject}"
                        ),
                    }
                )
        order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: (order.get(str(r["priority"]), 2), float(r["score"])))
        return recommendations[:n]

    def check_and_award_badges(
        self,
        profile: LearnerProfile,
        existing_badge_codes: list[str],
        context: dict[str, float] | None = None,
    ) -> list[BadgeRule]:
        """Retourne les badges nouvellement mérités.

        Args:
            profile: Profil à évaluer.
            existing_badge_codes: Codes déjà obtenus.
            context: Événements ponctuels (ex. ``{"exercise_score": 1.0}``).

        Returns:
            Les règles de badge nouvellement satisfaites.
        """
        context = context or {}
        owned = set(existing_badge_codes)
        earned: list[BadgeRule] = []
        for rule in BADGE_RULES:
            if rule.code in owned:
                continue
            if rule.condition is not None:
                if rule.condition(profile):
                    earned.append(rule)
            elif rule.code == "perfect_score" and context.get("exercise_score") == 1.0:
                earned.append(rule)
        return earned

    def get_zpd_difficulty(self, mastery_score: float) -> str:
        """Choisit la difficulté dans la zone proximale de développement."""
        if mastery_score < 0.30:
            return "debutant"
        if mastery_score < 0.55:
            return "intermediaire"
        if mastery_score < 0.80:
            return "avance"
        return "expert"


adaptive_service = AdaptiveLearningService()
