"""Exercices générés par l'IA : génération, correction par grille, révision guidée.

Idempotence (correctif P1) : la génération accepte un ``request_id`` ; la
soumission est protégée par une clé liée à l'exercice et par la contrainte
unique (utilisateur, exercice). Un double envoi ne rappelle donc pas l'IA.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user_id
from app.core.i18n import Lang, get_lang
from app.core.quota import consume_llm_quota
from app.core.rate_limit import llm_rate_limit
from app.core.security import enum_value
from app.db.database import get_db
from app.models.models import DifficultyLevel, Exercise, ExerciseAttempt, LearnerProfile
from app.schemas.chat import (
    AttemptResult,
    AttemptSubmit,
    ExerciseOut,
    ExerciseRequest,
    GuidedReviewItem,
    GuidedReviewPlan,
    GuidedReviewRequest,
    RubricScoreItem,
)
from app.services import exercise_service, idempotency, tutor_service
from app.services.adaptive_service import adaptive_service
from app.services.badge_service import award_new_badges, record_mastery_snapshot
from app.services.math_verify import verify_numeric_answer

router = APIRouter()

SCOPE_GENERATE = "exercise"
SCOPE_ATTEMPT = "attempt"


def _exercise_out(exercise: Exercise) -> ExerciseOut:
    return ExerciseOut(
        id=exercise.id,
        subject=enum_value(exercise.subject),
        level=enum_value(exercise.school_level),
        difficulty=enum_value(exercise.difficulty),
        topic=exercise.topic,
        statement=exercise.statement,
        hints=list(exercise.hints or []),
        concepts=list(exercise.concepts or []),
        estimated_min=exercise.estimated_min or 10,
    )


def _stored_result(exercise_id: str, attempt: ExerciseAttempt) -> AttemptResult:
    """Reconstruit le résultat d'une tentative déjà corrigée (sans rappeler l'IA)."""
    score = float(attempt.score or 0.0)
    return AttemptResult(
        exercise_id=exercise_id,
        score=score,
        correct=score >= 0.8,
        partial=0.3 <= score < 0.8,
        feedback=attempt.feedback or "",
        errors=[],
        concepts_to_review=[],
        positive_points=[],
    )


@router.post("/generate", response_model=ExerciseOut, dependencies=[Depends(llm_rate_limit)])
async def generate_exercise(
    body: ExerciseRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    lang: Lang = Depends(get_lang),
) -> ExerciseOut:
    """Génère un exercice adapté au niveau de maîtrise (zone proximale de développement)."""
    existing_id = await idempotency.claim(db, user_id, SCOPE_GENERATE, body.request_id)
    if existing_id:
        existing = await db.get(Exercise, existing_id)
        if existing is not None:
            return _exercise_out(existing)

    try:
        await consume_llm_quota(db, user_id)
        subject = body.subject.value
        profile = (
            await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user_id))
        ).scalar_one_or_none()
        # Difficulté calée sur le concept visé (repli : moyenne de la matière, puis 0,5).
        mastery = adaptive_service.concept_level(profile, subject, body.topic) if profile else 0.5
        difficulty = (
            body.difficulty.value if body.difficulty else adaptive_service.get_zpd_difficulty(mastery)
        )

        recent = await db.execute(
            select(Exercise.statement)
            .where(
                Exercise.subject == body.subject,
                Exercise.school_level == body.level,
                Exercise.topic == body.topic,
            )
            .order_by(Exercise.created_at.desc())
            .limit(6)
        )
        generated = await exercise_service.generate_exercise(
            subject, body.level.value, body.topic, difficulty, [s for (s,) in recent.all()], lang=lang
        )
        exercise = Exercise(
            subject=body.subject,
            school_level=body.level,
            difficulty=DifficultyLevel(difficulty),
            topic=body.topic,
            statement=generated.statement,
            solution=generated.solution,
            hints=generated.hints,
            concepts=generated.concepts or [body.topic],
            estimated_min=generated.estimated_min,
            numeric_answer=generated.numeric_answer,
            grading_rubric=generated.grading_rubric,
        )
        db.add(exercise)
        await db.flush()
        await idempotency.complete(db, user_id, SCOPE_GENERATE, body.request_id, exercise.id)
        await db.commit()
    except Exception:
        await idempotency.release(db, user_id, SCOPE_GENERATE, body.request_id)
        raise
    await db.refresh(exercise)
    return _exercise_out(exercise)


@router.post("/guided-review", response_model=GuidedReviewPlan)
async def guided_review(
    body: GuidedReviewRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    lang: Lang = Depends(get_lang),
) -> GuidedReviewPlan:
    """Plan de révision basé sur les lacunes (maîtrise effective, oubli appliqué)."""
    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user_id))
    ).scalar_one_or_none()
    if profile is None:
        return GuidedReviewPlan(items=[], has_gaps=False)
    recs = adaptive_service.get_recommendations(profile, n=8, lang=lang)
    if body.subject is not None:
        recs = [r for r in recs if r["subject"] == body.subject.value]
    items = [
        GuidedReviewItem(
            priority=r["priority"],
            subject=r["subject"],
            concept=r.get("concept"),
            score=r["score"],
            reason=r["reason"],
            action=r["action"],
        )
        for r in recs
    ]
    return GuidedReviewPlan(items=items, has_gaps=bool(items))


@router.post("/submit", response_model=AttemptResult, dependencies=[Depends(llm_rate_limit)])
async def submit_answer(
    body: AttemptSubmit,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    lang: Lang = Depends(get_lang),
) -> AttemptResult:
    """Corrige la réponse (grille + vérification numérique exacte). Une tentative par exercice."""
    exercise = await db.get(Exercise, body.exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercice introuvable.")

    previous = (
        await db.execute(
            select(ExerciseAttempt).where(
                ExerciseAttempt.user_id == user_id, ExerciseAttempt.exercise_id == exercise.id
            )
        )
    ).scalar_one_or_none()
    if previous is not None:
        return _stored_result(exercise.id, previous)

    # Verrou logique : empêche deux corrections IA simultanées du même exercice.
    if await idempotency.claim(db, user_id, SCOPE_ATTEMPT, exercise.id):
        previous = (
            await db.execute(
                select(ExerciseAttempt).where(
                    ExerciseAttempt.user_id == user_id, ExerciseAttempt.exercise_id == exercise.id
                )
            )
        ).scalar_one_or_none()
        if previous is not None:
            return _stored_result(exercise.id, previous)

    try:
        await consume_llm_quota(db, user_id)
        subject = enum_value(exercise.subject)
        hints_used = min(body.hints_used, len(exercise.hints or []))
        analysis = await tutor_service.analyze_answer(
            exercise.statement,
            body.answer,
            exercise.solution,
            subject,
            enum_value(exercise.school_level),
            grading_rubric=exercise.grading_rubric or None,
            lang=lang,
        )
        numeric = verify_numeric_answer(exercise.numeric_answer or "", body.answer, lang)
        if numeric["checked"] and numeric["note"]:
            analysis["feedback"] = (analysis["feedback"] + "\n\n" + numeric["note"]).strip()

        db.add(
            ExerciseAttempt(
                user_id=user_id,
                exercise_id=exercise.id,
                answer=body.answer,
                score=analysis["score"],
                feedback=analysis["feedback"],
                hints_used=hints_used,
                completed=True,
            )
        )
        profile = (
            await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user_id))
        ).scalar_one_or_none()
        if profile is not None and exercise.concepts:
            for concept in list(exercise.concepts)[:2]:
                adaptive_service.update_profile_after_interaction(
                    profile,
                    subject=subject,
                    topic=str(concept),
                    is_correct=analysis["correct"],
                    item_type="open",
                    hints_used=hints_used,
                )
                record_mastery_snapshot(db, user_id, subject, str(concept), profile)
            # Une seule « session » par exercice (pas via update_profile_..., qui compterait une question de plus).
            profile.total_sessions = (profile.total_sessions or 0) + 1
            await award_new_badges(
                db, user_id, profile, context={"exercise_score": analysis["score"]}, lang=lang
            )
        await db.commit()
    except Exception:
        await idempotency.release(db, user_id, SCOPE_ATTEMPT, exercise.id)
        raise

    return AttemptResult(
        exercise_id=exercise.id,
        score=analysis["score"],
        correct=analysis["correct"],
        partial=analysis["partial"],
        feedback=analysis["feedback"],
        errors=analysis["errors"],
        concepts_to_review=analysis["concepts_to_review"],
        positive_points=analysis["positive_points"],
        rubric_breakdown=[RubricScoreItem(**item) for item in analysis["rubric_breakdown"]],
    )
