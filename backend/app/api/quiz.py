"""Quiz adaptatif : questions QCM générées, correction instantanée, fin de session.

Idempotence : une question ne peut être répondue qu'une fois (un double clic ne
met pas la maîtrise BKT à jour deux fois) ; la génération accepte un
``request_id`` ; la fin de session est plafonnée par jour (anti-farm de badges).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user_id
from app.core.i18n import Lang, get_lang
from app.core.quota import QUIZ_SESSION_KIND, consume_llm_quota, try_consume
from app.core.rate_limit import llm_rate_limit
from app.core.security import enum_value
from app.core.timeutil import utcnow
from app.db.database import get_db
from app.models.models import LearnerProfile, QuizAttempt, SchoolLevel, Subject
from app.schemas.chat import CalibrationOut, QuizAnswer, QuizQuestion, QuizResult, QuizSessionOut
from app.services import idempotency, metacognition, question_bank, quiz_service
from app.services.adaptive_service import adaptive_service
from app.services.badge_service import award_new_badges, record_mastery_snapshot

router = APIRouter()

SCOPE_QUIZ = "quiz"
SCOPE_QUIZ_END = "quiz_end"


def _question_out(attempt: QuizAttempt) -> QuizQuestion:
    return QuizQuestion(
        id=attempt.id,
        question=attempt.question,
        options=list(attempt.options or []),
        subject=enum_value(attempt.subject),
        level=enum_value(attempt.school_level),
        topic=attempt.topic,
    )


@router.get("/generate", response_model=QuizQuestion, dependencies=[Depends(llm_rate_limit)])
async def generate_quiz(
    subject: Subject,
    level: SchoolLevel,
    topic: str = Query(min_length=1, max_length=200),
    request_id: str | None = Query(default=None, min_length=8, max_length=64),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    lang: Lang = Depends(get_lang),
) -> QuizQuestion:
    """Génère une question de QCM (la bonne réponse reste côté serveur)."""
    existing_id = await idempotency.claim(db, user_id, SCOPE_QUIZ, request_id)
    if existing_id:
        existing = await db.get(QuizAttempt, existing_id)
        if existing is not None and existing.user_id == user_id:
            return _question_out(existing)

    try:
        # 1) Banque : question validée NON vue → aucun appel LLM, aucun quota consommé.
        item = await question_bank.pick(db, user_id, subject, level, topic, lang)
        bank_id: str | None = None
        if item is not None:
            question = quiz_service.shuffle_options(
                quiz_service.GeneratedQuestion(
                    item.question, list(item.options or []), int(item.correct_index), item.explanation or ""
                )
            )
            bank_id = item.id
        else:
            # 2) Génération (+ vérification de la clé), puis ajout à la banque.
            await consume_llm_quota(db, user_id)
            recent = await db.execute(
                select(QuizAttempt.question)
                .where(
                    QuizAttempt.user_id == user_id,
                    QuizAttempt.subject == subject,
                    QuizAttempt.school_level == level,
                    QuizAttempt.topic == topic,
                )
                .order_by(QuizAttempt.created_at.desc())
                .limit(8)
            )
            question = await quiz_service.generate_question(
                subject.value, level.value, topic, avoid_questions=[q for (q,) in recent.all()], lang=lang
            )
            stored = await question_bank.store(db, subject, level, topic, lang, question)
            bank_id = stored.id if stored is not None else None
        attempt = QuizAttempt(
            user_id=user_id,
            subject=subject,
            school_level=level,
            topic=topic,
            question=question.question,
            options=question.options,
            correct_index=question.correct_index,
            explanation=question.explanation,
            bank_id=bank_id,
        )
        db.add(attempt)
        await db.flush()
        await idempotency.complete(db, user_id, SCOPE_QUIZ, request_id, attempt.id)
        await db.commit()
    except Exception:
        await idempotency.release(db, user_id, SCOPE_QUIZ, request_id)
        raise
    await db.refresh(attempt)
    return _question_out(attempt)


@router.post("/answer", response_model=QuizResult)
async def answer_quiz(
    body: QuizAnswer,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> QuizResult:
    """Corrige une réponse. Répondre deux fois renvoie le premier résultat sans double comptage."""
    attempt = (
        await db.execute(
            select(QuizAttempt).where(QuizAttempt.id == body.question_id, QuizAttempt.user_id == user_id)
        )
    ).scalar_one_or_none()
    if attempt is None or attempt.exam_session_id is not None:
        raise HTTPException(status_code=404, detail="Question introuvable.")

    if attempt.answer_index is not None:
        return QuizResult(
            question_id=attempt.id,
            correct=bool(attempt.is_correct),
            correct_index=attempt.correct_index,
            explanation=attempt.explanation or "Voir le cours.",
            calibration=metacognition.classify(attempt.confidence, bool(attempt.is_correct)),
        )

    is_correct = body.answer_index == attempt.correct_index
    attempt.answer_index = body.answer_index
    attempt.is_correct = is_correct
    attempt.justification = body.justification or None
    attempt.confidence = body.confidence
    attempt.answered_at = utcnow()

    consecutive_wrong = 0
    if not is_correct:
        rows = await db.execute(
            select(QuizAttempt.is_correct)
            .where(
                QuizAttempt.user_id == user_id,
                QuizAttempt.subject == attempt.subject,
                QuizAttempt.topic == attempt.topic,
                QuizAttempt.answer_index.is_not(None),
            )
            .order_by(QuizAttempt.answered_at.desc())
            .limit(10)
        )
        for (was_correct,) in rows.all():
            if was_correct is False:
                consecutive_wrong += 1
            else:
                break

    subject = enum_value(attempt.subject)
    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user_id))
    ).scalar_one_or_none()
    if profile is not None:
        adaptive_service.update_profile_after_interaction(
            profile,
            subject=subject,
            topic=attempt.topic,
            is_correct=is_correct,
            item_type="mcq",
            confidence=body.confidence,
        )
        record_mastery_snapshot(db, user_id, subject, attempt.topic, profile)
        await award_new_badges(db, user_id, profile)
    if attempt.bank_id:
        await question_bank.record_outcome(db, attempt.bank_id, is_correct)
    await db.commit()

    return QuizResult(
        question_id=attempt.id,
        correct=is_correct,
        correct_index=attempt.correct_index,
        explanation=attempt.explanation or "Voir le cours.",
        consecutive_wrong=consecutive_wrong,
        calibration=metacognition.classify(body.confidence, is_correct),
    )


@router.get("/calibration", response_model=CalibrationOut)
async def calibration(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> CalibrationOut:
    """Profil de calibration : surconfiance / sous-confiance sur les dernières réponses."""
    return CalibrationOut.model_validate(await metacognition.summary(db, user_id))


@router.post("/complete-session", response_model=QuizSessionOut)
async def complete_quiz_session(
    request_id: str | None = Query(default=None, min_length=8, max_length=64),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    lang: Lang = Depends(get_lang),
) -> QuizSessionOut:
    """Enregistre la fin d'un quiz (UNE fois par session ; plafonné par jour)."""
    if await idempotency.claim(db, user_id, SCOPE_QUIZ_END, request_id):
        return QuizSessionOut(ok=True)

    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user_id))
    ).scalar_one_or_none()
    if profile is None:
        await idempotency.release(db, user_id, SCOPE_QUIZ_END, request_id)
        return QuizSessionOut(ok=False)
    if not await try_consume(db, user_id, QUIZ_SESSION_KIND, settings.DAILY_QUIZ_SESSION_CAP):
        return QuizSessionOut(ok=True)

    profile.total_sessions = (profile.total_sessions or 0) + 1
    awarded = await award_new_badges(db, user_id, profile, lang=lang)
    await idempotency.complete(db, user_id, SCOPE_QUIZ_END, request_id, user_id)
    await db.commit()
    return QuizSessionOut(ok=True, new_badges=awarded)
