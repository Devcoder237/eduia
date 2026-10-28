"""Dépendances FastAPI d'authentification et d'autorisation.

Les rôles (``is_admin`` / ``is_teacher``) sont toujours relus en base : ils ne
sont jamais lus depuis le JWT. Un compte désactivé ou dont ``token_version`` a
changé perd l'accès immédiatement.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenType, decode_token
from app.db.database import get_db
from app.models.models import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Retourne l'utilisateur authentifié.

    Args:
        credentials: En-tête ``Authorization: Bearer``.
        db: Session de la requête.

    Returns:
        L'utilisateur actif correspondant au jeton.

    Raises:
        HTTPException: 401 si le jeton est absent, invalide, révoqué, ou le
            compte désactivé.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Connecte-toi pour continuer.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials, TokenType.ACCESS)
    user = await db.get(User, payload["sub"])
    if user is None or not user.is_active or int(user.token_version or 0) != int(payload.get("tv", -1)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ta session a expiré. Reconnecte-toi, s'il te plaît.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user_id(user: User = Depends(get_current_user)) -> str:
    """Retourne uniquement l'identifiant de l'utilisateur authentifié."""
    return str(user.id)


async def get_current_admin_id(user: User = Depends(get_current_user)) -> str:
    """Exige le rôle administrateur (relu en base).

    Raises:
        HTTPException: 403 si l'utilisateur n'est pas administrateur.
    """
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs.")
    return str(user.id)


async def get_current_teacher_id(user: User = Depends(get_current_user)) -> str:
    """Exige le rôle enseignant (distinct d'administrateur, relu en base).

    Raises:
        HTTPException: 403 si l'utilisateur n'est pas enseignant.
    """
    if not user.is_teacher:
        raise HTTPException(status_code=403, detail="Accès réservé aux enseignants.")
    return str(user.id)
