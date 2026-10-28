"""Examen blanc : série de QCM chronométrée CÔTÉ SERVEUR, sans indices.

Correctifs de l'audit :
- le chronomètre fait foi côté serveur (``expires_at`` ; réponse tardive refusée) ;
- l'ordre des questions repose sur ``exam_position`` (unique), plus sur un
  décompte fragile ;
- ``answer`` et ``finish`` sont idempotents (pas de double correction, pas de
  double mise à jour du profil) ;
- l'historique est chargé en 2 requêtes (plus de N+1) ;
- la note est calculée sur le nombre de questions PRÉVUES ;
- aucune correction n'est renvoyée avant ``/finish`` (conditions d'examen).
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id
from app.core.i18n import DEFAULT_LANG, Lang, get_lang
from app.core.quota import consume_llm_quota
from app.core.rate_limit import llm_rate_limit
from app.core.security import enum_value
from app.core.timeutil import ensure_utc, utcnow
from app.db.database import get_db
from app.models.models import ExamSession, LearnerProfile, QuizAttempt
from app.schemas.chat import (
    ExamAnswerOut,
    ExamAnswerRequest,
    ExamDetail,
    ExamQuestionOut,
    ExamResultOut,
    ExamStartOut,
    ExamStartRequest,
)
from app.services import idempotency, quiz_service
from app.services.adaptive_service import adaptive_service
from app.services.badge_service import award_new_badges
from app.theme_topics import get_default_topic

router = APIRouter()

SCOPE_EXAM = "exam"
GRACE = timedelta(seconds=5)


def _expires_at(exam: ExamSession) -> datetime:
    started = ensure_utc(exam.started_at) or utcnow()
    return started + timedelta(seconds=exam.duration_sec_planned or 600)


def _question_out(exam: ExamSession, attempt: QuizAttempt) -> ExamQuestionOut:
    return ExamQuestionOut(
        attempt_id=attempt.id,
        question=attempt.question,
        options=list(attempt.options or []),
        index=attempt.exam_position or 0,
        total=exam.question_count or 0,
    )


def _details(attempts: list[QuizAttempt]) -> list[ExamDetail]:
    return [
        ExamDetail(
            question=a.question,
            options=list(a.options or []),
            correct_index=a.correct_index,
            answer_index=a.answer_index,
            is_correct=a.is_correct,
            explanation=a.explanation,
        )
        for a in attempts
    ]


async def _new_question(
    db: AsyncSession, exam: ExamSession, position: int, avoid: list[str], lang: Lang = DEFAULT_LANG
) -> QuizAttempt:
    """Génère et enregistre la question ``position`` (sans valider la transaction)."""
    subject, level = enum_value(exam.subject), enum_value(exam.school_level)
    topic = get_default_topic(subject, level)
    question = await quiz_service.generate_question(subject, level, topic, avoid_questions=avoid, lang=lang)
    attempt = QuizAttempt(
        user_id=exam.user_id,
        subject=exam.subject,
        school_level=exam.school_level,
        topic=topic,
        question=question.question,
        options=question.options,
        correct_index=question.correct_index,
        explanation=question.explanation,
        exam_session_id=exam.id,
        exam_position=position,
    )
    db.add(attempt)
    return attempt


async def _recent_questions(db: AsyncSession, user_id: str, exam: ExamSession) -> list[str]:
    rows = await db.execute(
        select(QuizAttempt.question)
        .where(
            QuizAttempt.user_id == user_id,
            QuizAttempt.subject == exam.subject,
            QuizAttempt.school_level == exam.school_level,
        )
        .order_by(QuizAttempt.created_at.desc())
        .limit(10)
    )
    return [q for (q,) in rows.all()]


async def _get_exam(db: AsyncSession, exam_id: str, user_id: str) -> ExamSession:
    exam = (
        await db.execute(select(ExamSession).where(ExamSession.id == exam_id, ExamSession.user_id == user_id))
    ).scalar_one_or_none()
    if exam is None:
        raise HTTPException(status_code=404, detail="Examen introuvable.")
    return exam


@router.post("/start", response_model=ExamStartOut, dependencies=[Depends(llm_rate_limit)])
async def start_exam(
    body: ExamStartRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    lang: Lang = Depends(get_lang),
) -> ExamStartOut:
    """Démarre un examen blanc (idempotent grâce à ``request_id``)."""
    existing_id = await idempotency.claim(db, user_id, SCOPE_EXAM, body.request_id)
    if existing_id:
        exam = await db.get(ExamSession, existing_id)
        first = (
            await db.execute(
                select(QuizAttempt).where(
                    QuizAttempt.exam_session_id == existing_id, QuizAttempt.exam_position == 0
                )
            )
        ).scalar_one_or_none()
        if exam is not None and exam.user_id == user_id and first is not None:
            return ExamStartOut(
                exam_id=exam.id,
                duration_sec=exam.duration_sec_planned or 0,
                question_count=exam.question_count or 0,
                expires_at=_expires_at(exam),
                first_question=_question_out(exam, first),
            )

    try:
        await consume_llm_quota(db, user_id)
        exam = ExamSession(
            user_id=user_id,
            subject=body.subject,
            school_level=body.level,
            exam_label=body.exam_label,
            question_count=body.question_count,
            duration_sec_planned=body.duration_min * 60,
            started_at=utcnow(),
            status="in_progress",
        )
        db.add(exam)
        await db.flush()
        first = await _new_question(db, exam, 0, await _recent_questions(db, user_id, exam), lang)
        await db.flush()
        await idempotency.complete(db, user_id, SCOPE_EXAM, body.request_id, exam.id)
        await db.commit()
    except Exception:
        await idempotency.release(db, user_id, SCOPE_EXAM, body.request_id)
        raise
    await db.refresh(first)
    return ExamStartOut(
        exam_id=exam.id,
        duration_sec=exam.duration_sec_planned or 0,
        question_count=exam.question_count or 0,
        expires_at=_expires_at(exam),
        first_question=_question_out(exam, first),
    )


@router.post("/answer", response_model=ExamAnswerOut, dependencies=[Depends(llm_rate_limit)])
async def answer_exam_question(
    body: ExamAnswerRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    lang: Lang = Depends(get_lang),
) -> ExamAnswerOut:
    """Enregistre la réponse (``null`` = question passée) et renvoie la suivante."""
    attempt = (
        await db.execute(
            select(QuizAttempt).where(QuizAttempt.id == body.attempt_id, QuizAttempt.user_id == user_id)
        )
    ).scalar_one_or_none()
    if attempt is None or not attempt.exam_session_id:
        raise HTTPException(status_code=404, detail="Question d'examen introuvable.")
    exam = await _get_exam(db, attempt.exam_session_id, user_id)
    if exam.status != "in_progress":
        raise HTTPException(status_code=409, detail="Cet examen est déjà terminé.")

    if utcnow() > _expires_at(exam) + GRACE:
        return ExamAnswerOut(next_question=None, finished=True, time_expired=True)

    if attempt.answered_at is None:
        attempt.answered_at = utcnow()
        if body.answer_index is not None:
            attempt.answer_index = body.answer_index
            attempt.is_correct = body.answer_index == attempt.correct_index
        await db.commit()

    position = attempt.exam_position or 0
    if position + 1 >= (exam.question_count or 0):
        return ExamAnswerOut(next_question=None, finished=True)

    next_attempt = (
        await db.execute(
            select(QuizAttempt).where(
                QuizAttempt.exam_session_id == exam.id, QuizAttempt.exam_position == position + 1
            )
        )
    ).scalar_one_or_none()
    if next_attempt is None:
        await consume_llm_quota(db, user_id)
        previous = (
            await db.execute(select(QuizAttempt.question).where(QuizAttempt.exam_session_id == exam.id))
        ).all()
        avoid = [q for (q,) in previous] + await _recent_questions(db, user_id, exam)
        try:
            next_attempt = await _new_question(db, exam, position + 1, avoid[:10], lang)
            await db.commit()
        except IntegrityError:
            # Requête parallèle identique : on renvoie la question déjà créée.
            await db.rollback()
            next_attempt = (
                await db.execute(
                    select(QuizAttempt).where(
                        QuizAttempt.exam_session_id == exam.id, QuizAttempt.exam_position == position + 1
                    )
                )
            ).scalar_one()
        else:
            await db.refresh(next_attempt)
    return ExamAnswerOut(finished=False, next_question=_question_out(exam, next_attempt))


async def _build_result(exam: ExamSession, attempts: list[QuizAttempt], with_details: bool) -> ExamResultOut:
    correct = sum(1 for a in attempts if a.is_correct)
    total = exam.question_count or len(attempts)
    return ExamResultOut(
        exam_id=exam.id,
        subject=enum_value(exam.subject),
        level=enum_value(exam.school_level),
        exam_label=exam.exam_label or "",
        score=float(exam.score or 0.0),
        correct_count=correct,
        total=total,
        duration_sec=exam.duration_sec or 0,
        details=_details(attempts) if with_details else [],
    )


@router.post("/{exam_id}/finish", response_model=ExamResultOut)
async def finish_exam(
    exam_id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> ExamResultOut:
    """Termine l'examen et calcule la note (idempotent : le profil n'est mis à jour qu'une fois)."""
    exam = await _get_exam(db, exam_id, user_id)
    attempts = list(
        (
            await db.execute(
                select(QuizAttempt)
                .where(QuizAttempt.exam_session_id == exam_id)
                .order_by(QuizAttempt.exam_position.asc())
            )
        )
        .scalars()
        .all()
    )
    if exam.status == "completed":
        return await _build_result(exam, attempts, with_details=True)

    total = exam.question_count or len(attempts) or 1
    correct = sum(1 for a in attempts if a.is_correct)
    score = round(correct / total, 4)
    now = utcnow()
    started = ensure_utc(exam.started_at) or now
    exam.ended_at = now
    exam.duration_sec = int((now - started).total_seconds())
    exam.score = score
    exam.status = "completed"

    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user_id))
    ).scalar_one_or_none()
    if profile is not None:
        adaptive_service.update_profile_after_interaction(
            profile,
            subject=enum_value(exam.subject),
            topic=f"examen_{exam.exam_label}",
            score=score,
            new_session=True,
        )
        await award_new_badges(db, user_id, profile)
    await db.commit()
    return await _build_result(exam, attempts, with_details=True)


@router.get("/history", response_model=list[ExamResultOut])
async def exam_history(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> list[ExamResultOut]:
    """20 derniers examens terminés (2 requêtes, sans N+1)."""
    exams = list(
        (
            await db.execute(
                select(ExamSession)
                .where(ExamSession.user_id == user_id, ExamSession.status == "completed")
                .order_by(ExamSession.ended_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    if not exams:
        return []
    rows = await db.execute(select(QuizAttempt).where(QuizAttempt.exam_session_id.in_([e.id for e in exams])))
    by_exam: dict[str, list[QuizAttempt]] = {}
    for attempt in rows.scalars().all():
        by_exam.setdefault(str(attempt.exam_session_id), []).append(attempt)
    return [await _build_result(e, by_exam.get(e.id, []), with_details=False) for e in exams]
