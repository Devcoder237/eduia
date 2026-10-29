"""Temps d'activité réel : signaux de présence envoyés par le navigateur.

Protections contre les valeurs aberrantes :
- un signal vaut au plus 60 s ;
- dans une session en cours, le crédit ne dépasse jamais le temps écoulé depuis le signal précédent
  (+5 s de tolérance) : rejouer des signaux ne gonfle pas le temps ;
- au-delà de 10 min sans signal, une nouvelle session démarre.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id
from app.core.rate_limit import enforce
from app.core.timeutil import ensure_utc, utcnow
from app.db.database import get_db
from app.models.models import ActivitySession
from app.schemas.chat import HeartbeatIn

router = APIRouter()

SESSION_GAP = timedelta(minutes=10)
SLACK_SECONDS = 5
HEARTBEATS_PER_MINUTE = 20


@router.post("/heartbeat", status_code=204, response_class=Response)
async def heartbeat(
    body: HeartbeatIn,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Ajoute ``body.seconds`` de temps actif à la session en cours (ou en ouvre une).

    Args:
        body: Module utilisé et secondes d'activité écoulées depuis le dernier signal.
        user_id: Utilisateur connecté.
        db: Session de base de données.

    Returns:
        Une réponse vide (204).
    """
    enforce(f"beat:user:{user_id}", HEARTBEATS_PER_MINUTE, 60)
    now = utcnow()
    credit = body.seconds

    current = (
        await db.execute(
            select(ActivitySession)
            .where(ActivitySession.user_id == user_id)
            .order_by(ActivitySession.last_beat_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    last_beat = ensure_utc(current.last_beat_at) if current is not None else None
    if current is not None and last_beat is not None and now - last_beat <= SESSION_GAP:
        credit = min(credit, int((now - last_beat).total_seconds()) + SLACK_SECONDS)
        session = current
    else:
        session = ActivitySession(
            user_id=user_id,
            started_at=now - timedelta(seconds=credit),
            last_beat_at=now,
            active_sec=0,
            module_seconds={},
        )
        db.add(session)

    per_module = dict(session.module_seconds or {})
    per_module[body.module] = int(per_module.get(body.module, 0)) + credit
    session.module_seconds = per_module  # nouvel objet : SQLAlchemy détecte le changement du JSON
    session.active_sec = int(session.active_sec or 0) + credit
    session.last_beat_at = now
    await db.commit()
    return Response(status_code=204)