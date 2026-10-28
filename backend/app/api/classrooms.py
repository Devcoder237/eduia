"""Mode enseignant : classes, adhésion par code, rapports.

Confidentialité : un enseignant ne voit QUE les élèves ayant volontairement
rejoint une de SES classes. Les élèves peuvent quitter une classe à tout moment
(l'enseignant n'a alors plus accès à leurs données).
"""

import secrets
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_teacher_id, get_current_user_id
from app.core.rate_limit import enforce
from app.core.security import enum_value
from app.db.database import get_db
from app.models.models import Classroom, ClassroomMembership, LearnerProfile, User
from app.schemas.chat import (
    ClassAverage,
    ClassroomCreate,
    ClassroomJoin,
    ClassroomJoinOut,
    ClassroomOut,
    ClassroomReport,
    JoinedClassroom,
    StatusOut,
    StudentSummary,
    WeakConcept,
)
from app.services.adaptive_service import adaptive_service

router = APIRouter()

# Sans caractères ambigus (0/O, 1/I/L) : le code est écrit au tableau.
_INVITE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_invite_code() -> str:
    """Génère un code d'invitation de 6 caractères (aléa cryptographique)."""
    return "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(6))


def _classroom_out(c: Classroom, student_count: int) -> ClassroomOut:
    return ClassroomOut(
        id=c.id,
        name=c.name,
        invite_code=c.invite_code,
        level=enum_value(c.school_level),
        student_count=student_count,
        created_at=c.created_at,
    )


@router.post("/", response_model=ClassroomOut)
async def create_classroom(
    body: ClassroomCreate,
    teacher_id: str = Depends(get_current_teacher_id),
    db: AsyncSession = Depends(get_db),
) -> ClassroomOut:
    """Crée une classe avec un code d'invitation unique."""
    for _ in range(5):
        classroom = Classroom(
            teacher_id=teacher_id, name=body.name, invite_code=generate_invite_code(), school_level=body.level
        )
        db.add(classroom)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            continue
        await db.refresh(classroom)
        return _classroom_out(classroom, 0)
    raise HTTPException(
        status_code=500, detail="Impossible de générer un code d'invitation unique, réessaie."
    )


@router.get("/mine", response_model=list[ClassroomOut])
async def list_my_classrooms(
    teacher_id: str = Depends(get_current_teacher_id), db: AsyncSession = Depends(get_db)
) -> list[ClassroomOut]:
    """Classes de l'enseignant (effectifs en une requête)."""
    classrooms = (
        (
            await db.execute(
                select(Classroom)
                .where(Classroom.teacher_id == teacher_id, Classroom.is_active.is_(True))
                .order_by(Classroom.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    counts = (
        dict(
            (
                await db.execute(
                    select(ClassroomMembership.classroom_id, func.count())
                    .where(ClassroomMembership.classroom_id.in_([c.id for c in classrooms]))
                    .group_by(ClassroomMembership.classroom_id)
                )
            ).all()
        )
        if classrooms
        else {}
    )
    return [_classroom_out(c, int(counts.get(c.id, 0))) for c in classrooms]


@router.get("/joined", response_model=list[JoinedClassroom])
async def list_joined(
    user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> list[JoinedClassroom]:
    """Classes que l'élève a rejointes (il peut les quitter)."""
    rows = await db.execute(
        select(Classroom, ClassroomMembership.joined_at)
        .join(ClassroomMembership, ClassroomMembership.classroom_id == Classroom.id)
        .where(ClassroomMembership.student_id == user_id)
        .order_by(ClassroomMembership.joined_at.desc())
    )
    return [
        JoinedClassroom(id=c.id, name=c.name, level=enum_value(c.school_level), joined_at=joined)
        for c, joined in rows.all()
    ]


@router.post("/join", response_model=ClassroomJoinOut)
async def join_classroom(
    body: ClassroomJoin, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> ClassroomJoinOut:
    """Rejoint une classe par code (acte volontaire de l'élève ; limité contre le brute force)."""
    enforce(f"join:user:{user_id}", settings.RL_JOIN_PER_MIN, 60)
    classroom = (
        await db.execute(
            select(Classroom).where(
                Classroom.invite_code == body.invite_code.strip().upper(), Classroom.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if classroom is None:
        raise HTTPException(status_code=404, detail="Code d'invitation invalide ou classe inactive.")
    already = (
        await db.execute(
            select(ClassroomMembership.id).where(
                ClassroomMembership.classroom_id == classroom.id, ClassroomMembership.student_id == user_id
            )
        )
    ).first()
    if already:
        return ClassroomJoinOut(ok=True, already_member=True, classroom_name=classroom.name)
    db.add(ClassroomMembership(classroom_id=classroom.id, student_id=user_id))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return ClassroomJoinOut(ok=True, already_member=True, classroom_name=classroom.name)
    return ClassroomJoinOut(ok=True, already_member=False, classroom_name=classroom.name)


@router.delete("/membership/{classroom_id}", response_model=StatusOut)
async def leave_classroom(
    classroom_id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> StatusOut:
    """Quitte une classe : l'enseignant n'a plus accès aux données de l'élève."""
    result = await db.execute(
        delete(ClassroomMembership).where(
            ClassroomMembership.classroom_id == classroom_id, ClassroomMembership.student_id == user_id
        )
    )
    await db.commit()
    if not result.rowcount:  # type: ignore[attr-defined]
        raise HTTPException(status_code=404, detail="Tu ne fais pas partie de cette classe.")
    return StatusOut(status="Tu as quitté la classe.")


@router.get("/{classroom_id}/report", response_model=ClassroomReport)
async def get_classroom_report(
    classroom_id: str, teacher_id: str = Depends(get_current_teacher_id), db: AsyncSession = Depends(get_db)
) -> ClassroomReport:
    """Rapport de classe (autorisation stricte : il faut être l'enseignant de CETTE classe)."""
    classroom = (
        await db.execute(
            select(Classroom).where(Classroom.id == classroom_id, Classroom.teacher_id == teacher_id)
        )
    ).scalar_one_or_none()
    if classroom is None:
        raise HTTPException(status_code=404, detail="Classe introuvable.")

    rows = (
        await db.execute(
            select(ClassroomMembership.joined_at, User, LearnerProfile)
            .join(User, User.id == ClassroomMembership.student_id)
            .outerjoin(LearnerProfile, LearnerProfile.user_id == User.id)
            .where(ClassroomMembership.classroom_id == classroom_id)
            .order_by(ClassroomMembership.joined_at.asc())
        )
    ).all()

    students: list[StudentSummary] = []
    totals: dict[str, list[float]] = defaultdict(list)
    for joined_at, student, profile in rows:
        scores = {k: float(v) for k, v in ((profile.subject_scores if profile else None) or {}).items()}
        for subject, score in scores.items():
            totals[subject].append(score)
        weakest: list[WeakConcept] = []
        if profile is not None:
            weakest = sorted(
                (
                    WeakConcept(subject=subj, concept=concept, score=round(score, 3))
                    for subj, concepts in adaptive_service.get_effective_mastery(profile).items()
                    for concept, score in concepts.items()
                ),
                key=lambda w: w.score,
            )[:5]
        students.append(
            StudentSummary(
                user_id=student.id,
                full_name=student.full_name,
                username=student.username,
                total_sessions=(profile.total_sessions if profile else 0) or 0,
                total_questions=(profile.total_questions if profile else 0) or 0,
                streak_days=(profile.streak_days if profile else 0) or 0,
                subject_scores=scores,
                weakest_concepts=weakest,
                joined_at=joined_at,
            )
        )
    return ClassroomReport(
        classroom_id=classroom.id,
        classroom_name=classroom.name,
        student_count=len(students),
        students=students,
        class_averages=[
            ClassAverage(subject=s, average_score=round(sum(v) / len(v), 3)) for s, v in totals.items() if v
        ],
    )
