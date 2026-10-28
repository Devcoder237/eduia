"""Quotas quotidiens par utilisateur, stockés en base (survivent aux redémarrages).

Protège le crédit OpenAI : un compte scripté ne peut pas vider votre budget.
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.timeutil import today_local
from app.models.models import UsageCounter

LLM_KIND = "llm"
QUIZ_SESSION_KIND = "quiz_session"


async def _get_or_create(db: AsyncSession, user_id: str, kind: str) -> UsageCounter:
    """Retourne (en le créant au besoin) le compteur du jour pour l'utilisateur."""
    day = today_local()
    query = select(UsageCounter).where(
        UsageCounter.user_id == user_id, UsageCounter.day == day, UsageCounter.kind == kind
    )
    row = (await db.execute(query)).scalar_one_or_none()
    if row is not None:
        return row
    row = UsageCounter(user_id=user_id, day=day, kind=kind, count=0)
    db.add(row)
    try:
        await db.flush()
    except IntegrityError:
        # Course : une requête parallèle a créé la ligne entre-temps.
        await db.rollback()
        row = (await db.execute(query)).scalar_one()
    return row


async def try_consume(db: AsyncSession, user_id: str, kind: str, limit: int, units: int = 1) -> bool:
    """Consomme ``units`` du quota du jour si possible, et valide immédiatement.

    Args:
        db: Session de la requête.
        user_id: Utilisateur concerné.
        kind: Type de compteur.
        limit: Plafond quotidien.
        units: Nombre d'unités à consommer.

    Returns:
        ``True`` si consommé, ``False`` si le plafond serait dépassé.
    """
    row = await _get_or_create(db, user_id, kind)
    current = int(row.count or 0)
    if current + units > limit:
        await db.commit()
        return False
    row.count = current + units
    await db.commit()
    return True


async def consume_llm_quota(db: AsyncSession, user_id: str, units: int = 1) -> None:
    """Consomme du quota d'appels IA ou lève une 429.

    Args:
        db: Session de la requête.
        user_id: Utilisateur concerné.
        units: Nombre d'appels IA prévus.

    Raises:
        HTTPException: 429 si le quota quotidien est atteint.
    """
    if not await try_consume(db, user_id, LLM_KIND, settings.DAILY_LLM_QUOTA, units):
        raise HTTPException(
            status_code=429,
            detail="Tu as atteint ta limite d'aujourd'hui pour le tuteur IA. Reviens demain, "
            "et pense à réviser avec tes cahiers en attendant ! 📚",
        )
