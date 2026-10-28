"""Signalement des réponses du tuteur (erreur, contenu inapproprié, confusion)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id
from app.core.logging import get_logger
from app.core.rate_limit import enforce
from app.db.database import get_db
from app.models.models import ContentReport
from app.schemas.chat import ReportRequest, StatusOut

router = APIRouter()
log = get_logger(__name__)

REPORTS_PER_HOUR = 20


@router.post("", response_model=StatusOut, status_code=201)
async def create_report(
    body: ReportRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> StatusOut:
    """Enregistre un signalement (limité par utilisateur ; extrait court uniquement)."""
    enforce(f"report:user:{user_id}", REPORTS_PER_HOUR, 3600)
    db.add(
        ContentReport(
            user_id=user_id,
            session_id=body.session_id,
            reason=body.reason,
            excerpt=body.excerpt.strip(),
            comment=(body.comment or "").strip() or None,
        )
    )
    await db.commit()
    log.info("content_reported", reason=body.reason)  # aucun contenu ni identifiant dans les logs
    return StatusOut(status="ok")
