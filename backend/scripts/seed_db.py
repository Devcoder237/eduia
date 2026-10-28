"""Données de démonstration pour le DÉVELOPPEMENT (jamais de mot de passe public).

Usage : ``python -m scripts.seed_db``

- crée les badges (idempotent) ;
- crée un enseignant, deux élèves et une classe de démonstration, avec des mots de passe
  ALÉATOIRES affichés une seule fois dans ce terminal (rien n'est écrit dans le dépôt) ;
- refuse de s'exécuter en production.
"""

import asyncio
import secrets
import string
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.classrooms import generate_invite_code
from app.core.config import settings
from app.core.security import hash_password
from app.db import database as dbmod
from app.models.models import Classroom, ClassroomMembership, LearnerProfile, SchoolLevel, User
from app.services.badge_service import ensure_badges

_ALPHABET = string.ascii_letters + string.digits


def _random_password() -> str:
    """Mot de passe aléatoire conforme (majuscule + chiffre garantis)."""
    body = "".join(secrets.choice(_ALPHABET) for _ in range(14))
    return f"A1{body}"


async def _get_or_create(
    db: AsyncSession, email: str, username: str, full_name: str, teacher: bool
) -> tuple[User, str | None]:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is not None:
        return user, None
    password = _random_password()
    user = User(
        email=email,
        username=username,
        full_name=full_name,
        hashed_pwd=hash_password(password),
        is_active=True,
        is_verified=True,
        is_admin=False,
        is_teacher=teacher,
    )
    db.add(user)
    await db.flush()
    db.add(LearnerProfile(user_id=user.id))
    return user, password


async def main() -> int:
    """Insère les données de démonstration."""
    if settings.is_production:
        print("Refus : seed_db ne s'exécute pas en production.", file=sys.stderr)
        return 1
    async with dbmod.AsyncSessionLocal() as db:
        print(f"Badges créés : {await ensure_badges(db)}")
        teacher, t_pwd = await _get_or_create(db, "prof.demo@example.com", "prof_demo", "Prof Démo", True)
        s1, p1 = await _get_or_create(db, "eleve1.demo@example.com", "eleve1_demo", "Élève Un", False)
        s2, p2 = await _get_or_create(db, "eleve2.demo@example.com", "eleve2_demo", "Élève Deux", False)
        classroom = (
            (await db.execute(select(Classroom).where(Classroom.teacher_id == teacher.id))).scalars().first()
        )
        if classroom is None:
            classroom = Classroom(
                teacher_id=teacher.id,
                name="Classe démo",
                invite_code=generate_invite_code(),
                school_level=SchoolLevel.LYCEE,
            )
            db.add(classroom)
            await db.flush()
            db.add_all([ClassroomMembership(classroom_id=classroom.id, student_id=u.id) for u in (s1, s2)])
        await db.commit()
        print("\nComptes de démonstration (mots de passe affichés UNE SEULE FOIS) :")
        for user, pwd in ((teacher, t_pwd), (s1, p1), (s2, p2)):
            print(f"  {user.email:30s} {pwd or '(existe déjà : mot de passe inchangé)'}")
        print(f"\nCode d'invitation de la classe : {classroom.invite_code}")
    await dbmod.engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
