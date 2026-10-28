"""Tableau de bord administrateur : statistiques ANONYMISÉES et agrégées.

Jamais de contenu de conversation ni de donnée individuelle (utilisateurs en
grande partie mineurs). Agrégations faites en SQL (``GROUP BY``).
"""

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin_id
from app.core.security import enum_value
from app.core.timeutil import to_local_date, today_local, utcnow
from app.db.database import get_db
from app.models.models import Exercise, LearnerProfile, Message, QuizAttempt, TutorSession, User
from app.schemas.chat import AdminStats, DayCount, LevelCount, SubjectCount

router = APIRouter()


async def _count(db: AsyncSession, column: object) -> int:
    return int((await db.execute(select(func.count(column)))).scalar() or 0)  # type: ignore[arg-type]


@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    _: str = Depends(get_current_admin_id), db: AsyncSession = Depends(get_db)
) -> AdminStats:
    """Statistiques globales de la plateforme."""
    now = utcnow()
    active_7d = (
        await db.execute(
            select(func.count(func.distinct(TutorSession.user_id))).where(
                TutorSession.started_at >= now - timedelta(days=7)
            )
        )
    ).scalar() or 0

    subjects = (
        await db.execute(select(TutorSession.subject, func.count()).group_by(TutorSession.subject))
    ).all()
    levels = (
        await db.execute(
            select(LearnerProfile.school_level, func.count()).group_by(LearnerProfile.school_level)
        )
    ).all()

    signup_counts: dict[str, int] = {}
    for (created_at,) in (
        await db.execute(select(User.created_at).where(User.created_at >= now - timedelta(days=30)))
    ).all():
        day = to_local_date(created_at).isoformat()
        signup_counts[day] = signup_counts.get(day, 0) + 1
    today = today_local()

    return AdminStats(
        total_users=await _count(db, User.id),
        active_users_7d=int(active_7d),
        total_sessions=await _count(db, TutorSession.id),
        total_messages=await _count(db, Message.id),
        total_exercises=await _count(db, Exercise.id),
        total_quiz_attempts=await _count(db, QuizAttempt.id),
        subject_popularity=sorted(
            (SubjectCount(subject=enum_value(s), count=int(c)) for s, c in subjects), key=lambda x: -x.count
        ),
        level_distribution=sorted(
            (LevelCount(level=enum_value(lv), count=int(c)) for lv, c in levels), key=lambda x: -x.count
        ),
        signups_by_day=[
            DayCount(
                date=str(today - timedelta(days=i)),
                count=signup_counts.get(str(today - timedelta(days=i)), 0),
            )
            for i in range(29, -1, -1)
        ],
    )
