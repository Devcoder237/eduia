"""Types SQLAlchemy personnalisés (portables SQLite / PostgreSQL)."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

from app.core.timeutil import ensure_utc


class UTCDateTime(TypeDecorator[datetime]):
    """DateTime qui renvoie toujours un datetime UTC « aware ».

    SQLite restitue des datetimes naïfs alors que PostgreSQL les restitue
    « aware » : mélanger les deux fait planter les soustractions
    (``TypeError: can't subtract offset-naive and offset-aware``). Ce type
    uniformise le comportement sur les deux bases.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        """Convertit en UTC avant écriture (naïf = UTC)."""
        return ensure_utc(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        """Renvoie un datetime UTC « aware » à la lecture."""
        return ensure_utc(value)
