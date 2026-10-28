"""Crée (ou promeut) un compte administrateur ou enseignant, de façon interactive.

Usage (depuis ``backend/``, avec DATABASE_URL et SECRET_KEY définis) ::

    python -m scripts.create_admin                 # administrateur
    python -m scripts.create_admin --teacher       # enseignant
    python -m scripts.create_admin --email a@b.cd --username alice

Le mot de passe est saisi via ``getpass`` (jamais affiché, jamais en argument, jamais journalisé).
Si l'email existe déjà, le compte est promu (et son mot de passe inchangé).
"""

import argparse
import asyncio
import getpass
import sys

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from app.core.security import hash_password
from app.db import database as dbmod
from app.models.models import LearnerProfile, User
from app.schemas.chat import UserRegister

_REGISTER = TypeAdapter(UserRegister)


def _ask_password() -> str:
    """Demande un mot de passe valide (confirmation incluse)."""
    while True:
        first = getpass.getpass("Mot de passe (8+ car., 1 majuscule, 1 chiffre) : ")
        if first != getpass.getpass("Confirmez le mot de passe : "):
            print("Les mots de passe ne correspondent pas.", file=sys.stderr)
            continue
        return first


async def create(email: str, username: str, password: str | None, teacher: bool) -> str:
    """Crée ou promeut le compte et retourne un message de résultat."""
    async with dbmod.AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email.lower()))).scalar_one_or_none()
        if user is not None:
            user.is_teacher = user.is_teacher or teacher
            user.is_admin = user.is_admin or not teacher
            await db.commit()
            return f"Compte existant promu : {user.email}"
        if password is None:
            raise ValueError("Mot de passe requis pour un nouveau compte.")
        user = User(
            email=email.lower(),
            username=username,
            hashed_pwd=hash_password(password),
            is_active=True,
            is_verified=True,
            is_admin=not teacher,
            is_teacher=teacher,
        )
        db.add(user)
        await db.flush()
        db.add(LearnerProfile(user_id=user.id))
        await db.commit()
        return f"Compte créé : {user.email} ({'enseignant' if teacher else 'administrateur'})"


async def _main(args: argparse.Namespace) -> int:
    email = args.email or input("Email : ").strip()
    async with dbmod.AsyncSessionLocal() as db:
        exists = (await db.execute(select(User.id).where(User.email == email.lower()))).first() is not None
    username = args.username or ("" if exists else input("Nom d'utilisateur : ").strip())
    password = None if exists else _ask_password()
    if not exists:
        try:
            _REGISTER.validate_python({"email": email, "username": username, "password": password})
        except ValidationError as exc:
            print(f"Données invalides : {exc.errors()[0]['msg']}", file=sys.stderr)
            return 1
    try:
        print(await create(email, username, password, args.teacher))
    finally:
        await dbmod.engine.dispose()
    return 0


def main() -> None:
    """Point d'entrée en ligne de commande."""
    parser = argparse.ArgumentParser(description="Crée un compte administrateur ou enseignant.")
    parser.add_argument("--email")
    parser.add_argument("--username")
    parser.add_argument(
        "--teacher", action="store_true", help="créer un enseignant au lieu d'un administrateur"
    )
    sys.exit(asyncio.run(_main(parser.parse_args())))


if __name__ == "__main__":
    main()
