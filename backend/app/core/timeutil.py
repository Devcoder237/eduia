"""Utilitaires de date/heure.

Décision : le Cameroun est en UTC+1 toute l'année (pas d'heure d'été). On utilise
donc un décalage fixe plutôt que ``zoneinfo``, ce qui évite d'avoir à installer
``tzdata`` dans une image Docker « slim ». Toutes les dates stockées en base
sont en UTC ; seuls les calculs « par jour » (streak, calendrier d'activité,
quotas quotidiens) utilisent l'heure locale de l'élève.
"""

from datetime import UTC, date, datetime, timedelta, timezone

LOCAL_TZ = timezone(timedelta(hours=1), name="WAT")


def utcnow() -> datetime:
    """Retourne l'instant présent, en UTC, avec fuseau horaire.

    Returns:
        Un ``datetime`` « aware » en UTC.
    """
    return datetime.now(UTC)


def ensure_utc(value: datetime | None) -> datetime | None:
    """Normalise un datetime en UTC « aware ».

    Args:
        value: Un datetime naïf (supposé UTC), aware, ou ``None``.

    Returns:
        Le datetime converti en UTC, ou ``None`` si ``value`` est ``None``.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_local_date(value: datetime) -> date:
    """Convertit un instant en date calendaire locale (Cameroun, UTC+1).

    Args:
        value: Un datetime (naïf = UTC).

    Returns:
        La date locale correspondante.
    """
    aware = ensure_utc(value)
    assert aware is not None  # noqa: S101 - garanti par l'entrée non nulle
    return aware.astimezone(LOCAL_TZ).date()


def today_local() -> date:
    """Retourne la date du jour au Cameroun."""
    return to_local_date(utcnow())
