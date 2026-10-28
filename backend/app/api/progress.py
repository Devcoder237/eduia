"""Progression de l'élève : tableau de bord, statistiques, courbes de maîtrise."""

from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id
from app.core.i18n import Lang, get_lang, localize_badge
from app.core.security import enum_value
from app.core.timeutil import ensure_utc, to_local_date, today_local, utcnow
from app.db.database import get_db
from app.models.models import (
    Badge,
    ExamSession,
    ExerciseAttempt,
    LearnerProfile,
    MasteryHistory,
    Message,
    QuizAttempt,
    TutorSession,
    UserBadge,
)
from app.schemas.chat import (
    BadgeOut,
    DetailedStats,
    HeatmapCell,
    MasteryConceptOption,
    MasteryHistoryPoint,
    ProgressDashboard,
    RecentSession,
    Recommendation,
    SubjectScore,
    WeeklyStat,
)
from app.services.adaptive_service import adaptive_service

router = APIRouter()


def _activity_level(count: int) -> int:
    if count == 0:
        return 0
    if count <= 2:
        return 1
    if count <= 5:
        return 2
    return 3


async def _activity_by_day(db: AsyncSession, user_id: str, since: datetime) -> dict[str, int]:
    """Agrège l'activité réelle (tuteur, quiz, examens, exercices) par jour local."""
    queries = (
        select(Message.created_at)
        .join(TutorSession, Message.session_id == TutorSession.id)
        .where(TutorSession.user_id == user_id, Message.created_at >= since, Message.role == "user"),
        select(QuizAttempt.answered_at).where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.answered_at.is_not(None),
            QuizAttempt.answered_at >= since,
        ),
        select(ExamSession.ended_at).where(
            ExamSession.user_id == user_id, ExamSession.ended_at.is_not(None), ExamSession.ended_at >= since
        ),
        select(ExerciseAttempt.created_at).where(
            ExerciseAttempt.user_id == user_id, ExerciseAttempt.created_at >= since
        ),
    )
    counts: dict[str, int] = defaultdict(int)
    for query in queries:
        for (moment,) in (await db.execute(query)).all():
            if moment is not None:
                counts[to_local_date(moment).isoformat()] += 1
    return counts


TREND_WINDOW_DAYS = 14
TREND_THRESHOLD = 0.05


def compute_trend(recent: list[float], previous: list[float]) -> str:
    """Tendance (``up``/``down``/``stable``) en comparant deux fenêtres de 14 jours.

    Sans données dans les DEUX fenêtres, on ne prétend rien : ``stable``.
    """
    if not recent or not previous:
        return "stable"
    delta = sum(recent) / len(recent) - sum(previous) / len(previous)
    if delta > TREND_THRESHOLD:
        return "up"
    if delta < -TREND_THRESHOLD:
        return "down"
    return "stable"


async def _subject_trends(db: AsyncSession, user_id: str) -> dict[str, str]:
    """Tendance par matière à partir de l'historique de maîtrise (28 derniers jours)."""
    now = utcnow()
    boundary = now - timedelta(days=TREND_WINDOW_DAYS)
    rows = await db.execute(
        select(MasteryHistory.subject, MasteryHistory.score, MasteryHistory.recorded_at).where(
            MasteryHistory.user_id == user_id,
            MasteryHistory.recorded_at >= now - timedelta(days=2 * TREND_WINDOW_DAYS),
        )
    )
    recent: dict[str, list[float]] = defaultdict(list)
    previous: dict[str, list[float]] = defaultdict(list)
    for subject, score, recorded_at in rows.all():
        moment = ensure_utc(recorded_at)
        if moment is None:
            continue
        (recent if moment >= boundary else previous)[str(subject)].append(float(score))
    return {s: compute_trend(recent.get(s, []), previous.get(s, [])) for s in set(recent) | set(previous)}


@router.get("/dashboard", response_model=ProgressDashboard)
async def get_dashboard(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    lang: Lang = Depends(get_lang),
) -> ProgressDashboard:
    """Tableau de bord : scores, recommandations, badges, calendrier d'activité (28 jours)."""
    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user_id))
    ).scalar_one_or_none()
    if profile is None:
        return ProgressDashboard(
            total_sessions=0,
            total_questions=0,
            streak_days=0,
            subject_scores=[],
            recent_sessions=[],
            recommendations=[],
            badges=[],
            heatmap=[],
        )

    trends = await _subject_trends(db, user_id)
    subject_scores = [
        SubjectScore(subject=s, score=float(v), trend=trends.get(s, "stable"))
        for s, v in (profile.subject_scores or {}).items()
    ]
    recommendations = [
        Recommendation(
            priority=r["priority"],
            subject=r["subject"],
            concept=r.get("concept"),
            score=r["score"],
            reason=r["reason"],
            action=r["action"],
        )
        for r in adaptive_service.get_recommendations(profile, n=5, lang=lang)
    ]
    badge_rows = await db.execute(
        select(UserBadge, Badge)
        .join(Badge, UserBadge.badge_id == Badge.id)
        .where(UserBadge.user_id == user_id)
    )
    badges = [
        BadgeOut(
            code=b.code,
            name=localize_badge(b.code, b.name, b.description or "", lang)[0],
            icon=b.icon or "🏅",
            description=localize_badge(b.code, b.name, b.description or "", lang)[1],
            rarity=b.rarity or "common",
            earned_at=ub.earned_at,
        )
        for ub, b in badge_rows.all()
    ]

    today = today_local()
    counts = await _activity_by_day(db, user_id, utcnow() - timedelta(days=29))
    heatmap = [
        HeatmapCell(
            date=str(today - timedelta(days=i)),
            level=_activity_level(counts.get(str(today - timedelta(days=i)), 0)),
        )
        for i in range(27, -1, -1)
    ]
    sessions = (
        (
            await db.execute(
                select(TutorSession)
                .where(TutorSession.user_id == user_id)
                .order_by(TutorSession.started_at.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )
    recent = [
        RecentSession(
            id=s.id, subject=enum_value(s.subject), duration=s.duration_sec, started_at=str(s.started_at)
        )
        for s in sessions
    ]

    return ProgressDashboard(
        total_sessions=profile.total_sessions or 0,
        total_questions=profile.total_questions or 0,
        streak_days=profile.streak_days or 0,
        subject_scores=subject_scores,
        recent_sessions=recent,
        recommendations=recommendations,
        badges=badges,
        heatmap=heatmap,
    )


@router.get("/detailed-stats", response_model=DetailedStats)
async def get_detailed_stats(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> DetailedStats:
    """Temps moyen, progression hebdomadaire (8 semaines), répartition par matière."""
    rows = (
        await db.execute(
            select(TutorSession.subject, TutorSession.duration_sec).where(TutorSession.user_id == user_id)
        )
    ).all()
    durations = [d for _, d in rows if d]
    by_subject: dict[str, int] = defaultdict(int)
    for subject, _ in rows:
        by_subject[enum_value(subject)] += 1

    now = utcnow()
    quiz_rows = (
        await db.execute(
            select(QuizAttempt.created_at, QuizAttempt.is_correct).where(
                QuizAttempt.user_id == user_id,
                QuizAttempt.created_at >= now - timedelta(weeks=8),
                QuizAttempt.answered_at.is_not(None),
            )
        )
    ).all()
    weekly: dict[int, list[float]] = defaultdict(list)
    for created_at, is_correct in quiz_rows:
        weeks_ago = (now - created_at).days // 7
        if 0 <= weeks_ago < 8:
            weekly[weeks_ago].append(1.0 if is_correct else 0.0)
    weekly_progress = [
        WeeklyStat(
            week_label="Cette semaine" if w == 0 else f"Il y a {w} sem.",
            questions=len(weekly.get(w, [])),
            avg_score=round(sum(weekly[w]) / len(weekly[w]), 3) if weekly.get(w) else 0.0,
        )
        for w in range(7, -1, -1)
    ]

    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user_id))
    ).scalar_one_or_none()
    scores: dict[str, float] = dict(profile.subject_scores or {}) if profile else {}
    return DetailedStats(
        avg_session_min=round(sum(durations) / len(durations) / 60, 1) if durations else 0.0,
        total_time_min=round(sum(durations) / 60) if durations else 0,
        weekly_progress=weekly_progress,
        sessions_by_subject=dict(by_subject),
        best_subject=max(scores, key=lambda k: scores[k]) if scores else None,
        weakest_subject=min(scores, key=lambda k: scores[k]) if scores else None,
    )


@router.get("/mastery-concepts", response_model=list[MasteryConceptOption])
async def list_mastery_concepts(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> list[MasteryConceptOption]:
    """Concepts avec au moins 2 points d'historique (alimente le sélecteur de courbe)."""
    rows = await db.execute(
        select(MasteryHistory.subject, MasteryHistory.concept, MasteryHistory.score)
        .where(MasteryHistory.user_id == user_id)
        .order_by(MasteryHistory.recorded_at.asc())
    )
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for subject, concept, score in rows.all():
        grouped[(subject, concept)].append(float(score))
    return [
        MasteryConceptOption(subject=subj, concept=concept, points_count=len(vals), latest_score=vals[-1])
        for (subj, concept), vals in grouped.items()
        if len(vals) >= 2
    ]


@router.get("/mastery-history", response_model=list[MasteryHistoryPoint])
async def get_mastery_history(
    subject: str,
    concept: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[MasteryHistoryPoint]:
    """Courbe de maîtrise d'un concept (60 derniers points, ordre chronologique)."""
    rows = (
        await db.execute(
            select(MasteryHistory.recorded_at, MasteryHistory.score)
            .where(
                MasteryHistory.user_id == user_id,
                MasteryHistory.subject == subject,
                MasteryHistory.concept == concept,
            )
            .order_by(MasteryHistory.recorded_at.desc())
            .limit(60)
        )
    ).all()
    return [MasteryHistoryPoint(recorded_at=r, score=float(s)) for r, s in reversed(rows)]
