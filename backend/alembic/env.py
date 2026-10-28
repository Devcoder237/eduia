"""Environnement Alembic (asynchrone).

L'URL vient de ``DATABASE_URL`` via ``app.core.config`` et passe par la même
normalisation que l'application (Neon, asyncpg, pooler). ``alembic upgrade head``
est exécuté au démarrage du conteneur (voir Dockerfile).
"""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from app.core.config import settings
from app.db.database import Base, create_engine_from_url
from app.models import models  # noqa: F401  (enregistre les tables dans Base.metadata)

target_metadata = Base.metadata
DATABASE_URL = settings.MIGRATION_DATABASE_URL or settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Génère le SQL sans connexion (``alembic upgrade head --sql``)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Applique les migrations avec un moteur asynchrone sans pool."""
    engine = create_engine_from_url(DATABASE_URL)
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
