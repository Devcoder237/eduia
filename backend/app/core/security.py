"""Mots de passe (bcrypt) et jetons JWT (PyJWT).

Décision : PyJWT remplace ``python-jose`` (CVE-2024-33663/33664, projet peu
maintenu). Deux types de jetons : ``access`` (courte durée) et ``refresh``
(longue durée), tous deux liés à ``User.token_version`` pour pouvoir être
révoqués (changement de mot de passe, suppression de compte).
"""

import enum
import hashlib
import uuid
from datetime import timedelta
from typing import Any

import bcrypt
import jwt
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.timeutil import utcnow

BCRYPT_MAX_BYTES = 72

# Hash factice : comparé quand l'email est inconnu pour égaliser le temps de
# réponse (évite l'énumération de comptes par mesure du temps).
_DUMMY_HASH = bcrypt.hashpw(b"eduia-dummy-password", bcrypt.gensalt(rounds=12)).decode("utf-8")


class TokenType(enum.StrEnum):
    """Type de jeton JWT."""

    ACCESS = "access"
    REFRESH = "refresh"
    RESET = "reset"


def hash_password(password: str) -> str:
    """Hache un mot de passe avec bcrypt.

    Args:
        password: Mot de passe en clair (72 octets maximum, validé en amont).

    Returns:
        Le hash bcrypt encodé en UTF-8.

    Raises:
        ValueError: Si le mot de passe dépasse 72 octets.
    """
    raw = password.encode("utf-8")
    if len(raw) > BCRYPT_MAX_BYTES:
        raise ValueError("Mot de passe trop long (72 octets maximum).")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    """Vérifie un mot de passe en temps constant.

    Si ``hashed`` est ``None`` (utilisateur inconnu), compare quand même avec un
    hash factice, puis renvoie ``False``.

    Args:
        plain: Mot de passe saisi.
        hashed: Hash stocké, ou ``None``.

    Returns:
        ``True`` si le mot de passe est correct.
    """
    raw = plain.encode("utf-8")[:BCRYPT_MAX_BYTES]
    target = hashed if hashed else _DUMMY_HASH
    try:
        ok = bcrypt.checkpw(raw, target.encode("utf-8"))
    except ValueError:
        return False
    return ok and hashed is not None


def create_token(user_id: str, token_version: int, token_type: TokenType) -> tuple[str, int]:
    """Crée un jeton JWT signé.

    Args:
        user_id: Identifiant de l'utilisateur (claim ``sub``).
        token_version: Version de jeton de l'utilisateur (claim ``tv``).
        token_type: ``ACCESS`` ou ``REFRESH``.

    Returns:
        Un tuple ``(jeton, durée_de_validité_en_secondes)``.
    """
    lifetime = (
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        if token_type is TokenType.ACCESS
        else timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    now = utcnow()
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": token_type.value,
        "tv": token_version,
        "iat": now,
        "exp": now + lifetime,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, int(lifetime.total_seconds())


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Décode et valide un jeton JWT.

    Args:
        token: Jeton brut.
        expected_type: Type attendu (un refresh ne peut pas servir d'access).

    Returns:
        Les claims du jeton.

    Raises:
        HTTPException: 401 si le jeton est invalide, expiré ou du mauvais type.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ta session a expiré. Reconnecte-toi, s'il te plaît.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise unauthorized from exc
    if payload.get("type") != expected_type.value:
        raise unauthorized
    return payload


def password_fingerprint(hashed_password: str | None) -> str:
    """Empreinte courte du hash actuel : un lien de réinitialisation devient invalide dès que le mot
    de passe change (usage unique), sans stocker le lien en base."""
    return hashlib.sha256((hashed_password or "").encode("utf-8")).hexdigest()[:16]


def create_reset_token(user_id: str, token_version: int, hashed_password: str | None) -> str:
    """Crée le jeton du lien « mot de passe oublié » (courte durée, usage unique).

    Args:
        user_id: Identifiant de l'utilisateur (claim ``sub``).
        token_version: Version de jeton actuelle (changer de mot de passe la fait évoluer).
        hashed_password: Hash actuel du mot de passe (sert à l'usage unique).

    Returns:
        Le jeton signé (distinct d'un jeton d'accès : le type ``reset`` est refusé ailleurs).
    """
    now = utcnow()
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": TokenType.RESET.value,
        "tv": token_version,
        "pwd": password_fingerprint(hashed_password),
        "iat": now,
        "exp": now + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_reset_token(token: str) -> dict[str, Any]:
    """Décode un jeton de réinitialisation.

    Raises:
        HTTPException: 400 si le jeton est invalide, expiré ou d'un autre type.
    """
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Ce lien est invalide ou a expiré. Demande un nouveau lien.",
    )
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub", "type", "pwd"]},
        )
    except jwt.PyJWTError as exc:
        raise invalid from exc
    if payload.get("type") != TokenType.RESET.value:
        raise invalid
    return payload


def enum_value(value: object) -> str:
    """Retourne la valeur textuelle d'un Enum (ou ``str(value)``).

    Args:
        value: Un Enum, une chaîne ou ``None``.

    Returns:
        La valeur sous forme de chaîne (``""`` pour ``None``).
    """
    if value is None:
        return ""
    inner = getattr(value, "value", value)
    return str(inner)
