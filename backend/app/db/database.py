"""Moteur et sessions SQLAlchemy asynchrones.

Compatible Neon (PostgreSQL gratuit, avec pooler PgBouncer) et SQLite (tests /
développement). L'URL fournie par Neon (``postgresql://...?sslmode=require``)
est convertie automatiquement pour le pilote asyncpg.
"""

import ssl
import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    """Base déclarative commune à tous les modèles."""


def normalize_database_url(raw_url: str) -> tuple[URL, dict[str, Any]]:
    """Adapte une URL de base de données au pilote asynchrone.

    - ``postgres://`` / ``postgresql://`` → ``postgresql+asyncpg://``
    - supprime ``sslmode`` / ``channel_binding`` (non gérés par asyncpg) et
      active TLS via ``connect_args['ssl']`` ;
    - sur un hôte « pooler » (PgBouncer, mode transaction) : désactive le cache
      des requêtes préparées, sinon erreurs ``prepared statement does not exist``.

    Args:
        raw_url: URL brute (variable ``DATABASE_URL``).

    Returns:
        Un tuple ``(url_normalisée, connect_args)``.
    """
    url = make_url(raw_url)
    connect_args: dict[str, Any] = {}

    if url.drivername in {"postgres", "postgresql", "postgresql+psycopg2", "postgresql+asyncpg"}:
        sslmode = url.query.get("sslmode")
        url = url.set(drivername="postgresql+asyncpg")
        url = url.difference_update_query(["sslmode", "channel_binding"])
        host = url.host or ""
        if sslmode in {"require", "verify-ca", "verify-full"} or host.endswith(".neon.tech"):
            connect_args["ssl"] = ssl.create_default_context()
        if "-pooler" in host:
            connect_args["statement_cache_size"] = 0
            connect_args["prepared_statement_cache_size"] = 0
            connect_args["prepared_statement_name_func"] = lambda: f"__asyncpg_{uuid.uuid4()}__"
    return url, connect_args


def create_engine_from_url(raw_url: str) -> AsyncEngine:
    """Crée un moteur asynchrone adapté à l'URL donnée.

    Args:
        raw_url: URL de base de données.

    Returns:
        Un ``AsyncEngine`` configuré (pool réduit pour Neon free).
    """
    url, connect_args = normalize_database_url(raw_url)
    if url.get_backend_name() == "sqlite":
        kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
        if url.database in (None, "", ":memory:"):
            kwargs["poolclass"] = StaticPool  # une seule connexion partagée (tests)
        return create_async_engine(url, **kwargs)
    return create_async_engine(
        url,
        connect_args=connect_args,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,  # Neon suspend les connexions inactives
        pool_recycle=settings.DB_POOL_RECYCLE_S,
    )


engine: AsyncEngine = create_engine_from_url(settings.DATABASE_URL)
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


def init_engine(raw_url: str) -> AsyncEngine:
    """Remplace le moteur global (utilisé par les tests).

    Args:
        raw_url: Nouvelle URL de base de données.

    Returns:
        Le nouveau moteur.
    """
    global engine, AsyncSessionLocal  # noqa: PLW0603
    engine = create_engine_from_url(raw_url)
    AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return engine


async def get_db() -> AsyncIterator[AsyncSession]:
    """Dépendance FastAPI : une session par requête, rollback en cas d'erreur.

    Yields:
        Une ``AsyncSession`` liée à la requête courante.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
