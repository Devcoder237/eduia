"""Limitation de débit en mémoire (fenêtre glissante).

Décision : pas de Redis (payant/complexe en gratuit). Render free exécute une
seule instance : un compteur en mémoire est donc cohérent. Limite connue : il
est remis à zéro à chaque redémarrage/réveil du service ; les quotas
*quotidiens* (coût OpenAI) sont, eux, stockés en base (``core/quota.py``).
"""

import hashlib
import time
from collections import deque
from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Request

from app.core.config import settings
from app.core.deps import get_current_user_id

_MAX_KEYS = 20_000


class SlidingWindowLimiter:
    """Compteur à fenêtre glissante, clé → horodatages des requêtes récentes."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}

    def reset(self) -> None:
        """Vide tous les compteurs (utilisé par les tests)."""
        self._hits.clear()

    def check(self, key: str, limit: int, window_s: int) -> int | None:
        """Enregistre une requête et indique si la limite est dépassée.

        Args:
            key: Identifiant de la ressource limitée (ex. ``login:ip:1.2.3.4``).
            limit: Nombre maximal de requêtes dans la fenêtre.
            window_s: Taille de la fenêtre en secondes.

        Returns:
            ``None`` si la requête est autorisée, sinon le nombre de secondes à
            attendre avant de réessayer.
        """
        now = time.monotonic()
        if len(self._hits) > _MAX_KEYS:
            self._purge(now, window_s)
        bucket = self._hits.setdefault(key, deque())
        while bucket and now - bucket[0] > window_s:
            bucket.popleft()
        if len(bucket) >= limit:
            return max(1, int(window_s - (now - bucket[0])) + 1)
        bucket.append(now)
        return None

    def _purge(self, now: float, window_s: int) -> None:
        """Supprime les clés inactives pour borner la mémoire."""
        stale = [k for k, b in self._hits.items() if not b or now - b[-1] > window_s]
        for key in stale:
            del self._hits[key]


limiter = SlidingWindowLimiter()


def too_many_requests(retry_after: int) -> HTTPException:
    """Construit l'erreur 429 (message bienveillant + en-tête Retry-After)."""
    return HTTPException(
        status_code=429,
        detail="Doucement, tu vas trop vite ! Attends un petit moment avant de réessayer.",
        headers={"Retry-After": str(retry_after)},
    )


def enforce(key: str, limit: int, window_s: int) -> None:
    """Applique la limite ou lève une 429 (no-op si désactivée).

    Args:
        key: Clé de limitation.
        limit: Requêtes maximales par fenêtre.
        window_s: Fenêtre en secondes.

    Raises:
        HTTPException: 429 si la limite est dépassée.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return
    retry_after = limiter.check(key, limit, window_s)
    if retry_after is not None:
        raise too_many_requests(retry_after)


def hash_key(value: str) -> str:
    """Hache une valeur sensible (email) pour l'utiliser comme clé, sans PII en mémoire."""
    return hashlib.sha256(value.lower().encode("utf-8")).hexdigest()[:16]


def client_ip(request: Request) -> str:
    """Retourne l'IP du client (uvicorn applique X-Forwarded-For via --proxy-headers)."""
    return request.client.host if request.client else "unknown"


def ip_rate_limit(
    scope: str, limit: Callable[[], int], window_s: int
) -> Callable[[Request], Awaitable[None]]:
    """Fabrique une dépendance limitant par adresse IP.

    Args:
        scope: Nom de la limite (ex. ``register``).
        limit: Fonction renvoyant la limite (lue à chaque appel, utile aux tests).
        window_s: Fenêtre en secondes.

    Returns:
        Une dépendance FastAPI.
    """

    async def _dependency(request: Request) -> None:
        enforce(f"{scope}:ip:{client_ip(request)}", limit(), window_s)

    return _dependency


def user_rate_limit(scope: str, limit: Callable[[], int], window_s: int) -> Callable[[str], Awaitable[None]]:
    """Fabrique une dépendance limitant par utilisateur authentifié.

    Args:
        scope: Nom de la limite (ex. ``llm``).
        limit: Fonction renvoyant la limite.
        window_s: Fenêtre en secondes.

    Returns:
        Une dépendance FastAPI.
    """

    async def _dependency(user_id: str = Depends(get_current_user_id)) -> None:
        enforce(f"{scope}:user:{user_id}", limit(), window_s)

    return _dependency


# Limite partagée par tous les endpoints qui appellent l'IA (par utilisateur).
llm_rate_limit = user_rate_limit("llm", lambda: settings.RL_LLM_PER_MIN, 60)
