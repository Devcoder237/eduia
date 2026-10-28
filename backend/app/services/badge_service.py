"""Badges et historique de maîtrise.

À appeler juste après une mise à jour du profil, AVANT le ``commit`` de
l'appelant (même transaction).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import DEFAULT_LANG, Lang, localize_badge
from app.models.models import Badge, LearnerProfile, MasteryHistory, UserBadge
from app.schemas.chat import BadgeOut
from app.services.adaptive_service import BADGE_RULES, adaptive_service


def record_mastery_snapshot(
    db: AsyncSession, user_id: str, subject: str, concept: str, profile: LearnerProfile
) -> None:
    """Enregistre UN point d'historique pour le concept qui vient d'être mis à jour.

    Args:
        db: Session courante.
        user_id: Propriétaire du profil.
        subject: Matière.
        concept: Concept mis à jour.
        profile: Profil déjà mis à jour.
    """
    score = (profile.concept_mastery or {}).get(subject, {}).get(concept)
    if score is not None:
        db.add(MasteryHistory(user_id=user_id, subject=subject, concept=concept, score=float(score)))


async def ensure_badges(db: AsyncSession) -> int:
    """Crée les définitions de badges manquantes (idempotent).

    Appelé au démarrage de l'application : aucun script de seed n'est requis
    pour que les badges fonctionnent.

    Args:
        db: Session ouverte.

    Returns:
        Le nombre de badges créés.
    """
    existing = {code for (code,) in (await db.execute(select(Badge.code))).all()}
    created = 0
    for rule in BADGE_RULES:
        if rule.code not in existing:
            db.add(
                Badge(
                    code=rule.code,
                    name=rule.name,
                    icon=rule.icon,
                    description=rule.description,
                    rarity=rule.rarity,
                )
            )
            created += 1
    if created:
        await db.commit()
    return created


async def award_new_badges(
    db: AsyncSession,
    user_id: str,
    profile: LearnerProfile,
    context: dict[str, float] | None = None,
    lang: Lang = DEFAULT_LANG,
) -> list[BadgeOut]:
    """Persiste les nouveaux badges mérités et les renvoie.

    Args:
        db: Session courante.
        user_id: Utilisateur.
        profile: Profil à jour.
        context: Événements ponctuels (ex. ``{"exercise_score": 1.0}``).
        lang: Langue du nom et de la description renvoyés.

    Returns:
        Les badges nouvellement obtenus.
    """
    rows = await db.execute(
        select(Badge.code).join(UserBadge, UserBadge.badge_id == Badge.id).where(UserBadge.user_id == user_id)
    )
    existing_codes = [code for (code,) in rows.all()]
    earned = adaptive_service.check_and_award_badges(profile, existing_codes, context=context)
    if not earned:
        return []

    badges = (await db.execute(select(Badge).where(Badge.code.in_([r.code for r in earned])))).scalars().all()
    by_code = {b.code: b for b in badges}
    awarded: list[BadgeOut] = []
    for rule in earned:
        badge = by_code.get(rule.code)
        if badge is None:
            continue
        db.add(UserBadge(user_id=user_id, badge_id=badge.id))
        name, description = localize_badge(rule.code, rule.name, rule.description, lang)
        awarded.append(
            BadgeOut(
                code=rule.code,
                name=name,
                icon=rule.icon,
                description=description,
                rarity=rule.rarity,
                earned_at=None,
            )
        )
    return awarded
