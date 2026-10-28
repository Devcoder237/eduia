"""Idempotence des endpoints coûteux (génération IA).

Principe : le client envoie un ``request_id`` (UUID) stable pour une même action
(ex. double clic, réessai réseau). Le premier appel « réserve » la clé, génère la
ressource, puis l'enregistre ; les appels suivants renvoient la même ressource
sans rappeler l'IA (donc sans consommer de quota ni d'argent).
"""

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import ensure_utc, utcnow
from app.models.models import IdempotencyKey

STALE_AFTER = timedelta(minutes=2)


async def _find(db: AsyncSession, user_id: str, scope: str, key: str) -> IdempotencyKey | None:
    query = select(IdempotencyKey).where(
        IdempotencyKey.user_id == user_id, IdempotencyKey.scope == scope, IdempotencyKey.key == key
    )
    return (await db.execute(query)).scalar_one_or_none()


async def claim(db: AsyncSession, user_id: str, scope: str, key: str | None) -> str | None:
    """Réserve une clé d'idempotence.

    Args:
        db: Session de la requête.
        user_id: Utilisateur.
        scope: Type d'action (``exercise``, ``quiz``, ``exam``...).
        key: ``request_id`` fourni par le client (``None`` = pas d'idempotence).

    Returns:
        L'identifiant de la ressource déjà créée si la clé est connue, sinon
        ``None`` (la clé vient d'être réservée : l'appelant doit créer la
        ressource puis appeler :func:`complete`).

    Raises:
        HTTPException: 409 si une requête identique est encore en cours.
    """
    if not key:
        return None
    existing = await _find(db, user_id, scope, key)
    if existing is not None:
        if existing.resource_id:
            return str(existing.resource_id)
        created = ensure_utc(existing.created_at)
        if created is not None and utcnow() - created < STALE_AFTER:
            raise HTTPException(status_code=409, detail="Cette demande est déjà en cours de traitement.")
        await db.execute(delete(IdempotencyKey).where(IdempotencyKey.id == existing.id))
    db.add(IdempotencyKey(user_id=user_id, scope=scope, key=key))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raced = await _find(db, user_id, scope, key)
        if raced is not None and raced.resource_id:
            return str(raced.resource_id)
        raise HTTPException(
            status_code=409, detail="Cette demande est déjà en cours de traitement."
        ) from None
    return None


async def complete(db: AsyncSession, user_id: str, scope: str, key: str | None, resource_id: str) -> None:
    """Associe la ressource créée à la clé (dans la transaction de l'appelant)."""
    if not key:
        return
    row = await _find(db, user_id, scope, key)
    if row is not None:
        row.resource_id = resource_id


async def release(db: AsyncSession, user_id: str, scope: str, key: str | None) -> None:
    """Libère une clé réservée si la génération a échoué (le client pourra réessayer)."""
    if not key:
        return
    await db.rollback()
    await db.execute(
        delete(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.scope == scope,
            IdempotencyKey.key == key,
            IdempotencyKey.resource_id.is_(None),
        )
    )
    await db.commit()
