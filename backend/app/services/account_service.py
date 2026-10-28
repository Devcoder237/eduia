"""Opérations de compte : création, suppression (RGPD)."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Classroom,
    ClassroomMembership,
    ContentReport,
    ExamSession,
    ExerciseAttempt,
    IdempotencyKey,
    LearnerProfile,
    MasteryHistory,
    Message,
    QuizAttempt,
    StudyPlan,
    TutorSession,
    UsageCounter,
    User,
    UserBadge,
)


async def delete_account(db: AsyncSession, user_id: str) -> None:
    """Supprime définitivement un compte et toutes ses données personnelles.

    L'ordre respecte les clés étrangères. Les exercices générés (banque commune,
    sans donnée personnelle) sont conservés. La transaction est validée par
    l'appelant (tout ou rien).

    Args:
        db: Session courante.
        user_id: Identifiant du compte à supprimer.
    """
    own_sessions = select(TutorSession.id).where(TutorSession.user_id == user_id)
    own_classrooms = select(Classroom.id).where(Classroom.teacher_id == user_id)

    await db.execute(delete(Message).where(Message.session_id.in_(own_sessions)))
    await db.execute(delete(TutorSession).where(TutorSession.user_id == user_id))
    await db.execute(delete(QuizAttempt).where(QuizAttempt.user_id == user_id))
    await db.execute(delete(ExamSession).where(ExamSession.user_id == user_id))
    await db.execute(delete(ExerciseAttempt).where(ExerciseAttempt.user_id == user_id))
    await db.execute(delete(MasteryHistory).where(MasteryHistory.user_id == user_id))
    await db.execute(delete(UserBadge).where(UserBadge.user_id == user_id))
    await db.execute(delete(StudyPlan).where(StudyPlan.user_id == user_id))
    await db.execute(delete(ContentReport).where(ContentReport.user_id == user_id))
    await db.execute(delete(UsageCounter).where(UsageCounter.user_id == user_id))
    await db.execute(delete(IdempotencyKey).where(IdempotencyKey.user_id == user_id))
    await db.execute(delete(ClassroomMembership).where(ClassroomMembership.student_id == user_id))
    await db.execute(delete(ClassroomMembership).where(ClassroomMembership.classroom_id.in_(own_classrooms)))
    await db.execute(delete(Classroom).where(Classroom.teacher_id == user_id))
    await db.execute(delete(LearnerProfile).where(LearnerProfile.user_id == user_id))
    await db.execute(delete(User).where(User.id == user_id))
