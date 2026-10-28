"""Journalisation structurée (structlog) sans données personnelles.

Règle : on journalise des identifiants techniques (``user_id``, ``request_id``,
codes, durées), jamais d'email, de nom, de mot de passe, de jeton, ni du contenu
des messages/réponses des élèves (mineurs). Un processeur supprime en plus tout
champ sensible par sécurité.
"""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

_SENSITIVE_KEYS = frozenset(
    {
        "email",
        "password",
        "new_password",
        "current_password",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "full_name",
        "username",
        "answer",
        "message",
        "content",
        "document_context",
        "justification",
    }
)


def _redact_pii(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    """Supprime les champs potentiellement personnels d'un événement de log."""
    for key in list(event_dict):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "[redacted]"
    return event_dict


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Configure structlog et la journalisation standard.

    Args:
        level: Niveau minimal (``INFO``, ``DEBUG``...).
        json_output: ``True`` pour du JSON (production), sinon rendu console.
    """
    numeric_level = logging.getLevelName(level.upper())
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=numeric_level)

    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_pii,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.typing.FilteringBoundLogger:
    """Retourne un logger structuré.

    Args:
        name: Nom du module (``__name__``).

    Returns:
        Un logger lié au nom donné.
    """
    return structlog.get_logger(name)  # type: ignore[no-any-return]
