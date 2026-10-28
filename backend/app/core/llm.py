"""Client LLM unique (OpenAI) : timeouts, retries, JSON strict, anti-injection.

Tous les appels IA de l'application passent par ce module (jamais de client
créé « à la volée » dans un routeur). Les services l'utilisent via
``from app.core import llm`` puis ``llm.complete_json(...)``, ce qui permet aux
tests de le remplacer (monkeypatch) sans réseau.
"""

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import openai
from fastapi import HTTPException

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

Message = dict[str, str]

_client: openai.AsyncOpenAI | None = None

_FENCE_RE = re.compile(r"<<<[^>]{0,60}>>>|```")
_JSON_FENCE_RE = re.compile(r"```(?:json)?")


class LLMError(HTTPException):
    """Erreur du fournisseur IA, convertie en réponse HTTP bienveillante."""


def _unavailable(detail: str, code: int = 503) -> LLMError:
    return LLMError(status_code=code, detail=detail)


def get_client() -> openai.AsyncOpenAI:
    """Retourne le client OpenAI (créé paresseusement, timeout et retries bornés).

    Raises:
        LLMError: 503 si aucune clé API n'est configurée.
    """
    global _client
    if not settings.OPENAI_API_KEY:
        raise _unavailable("Le tuteur IA n'est pas disponible pour le moment. Réessaie plus tard.")
    if _client is None:
        _client = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.LLM_TIMEOUT_S,
            max_retries=settings.LLM_MAX_RETRIES,
        )
    return _client


def reset_client() -> None:
    """Oublie le client en cache (utilisé par les tests)."""
    global _client
    _client = None


def _translate(exc: Exception) -> LLMError:
    """Convertit une exception du SDK OpenAI en erreur HTTP lisible (sans fuite de détails)."""
    if isinstance(exc, openai.RateLimitError):
        return _unavailable("Le tuteur IA est très sollicité en ce moment. Réessaie dans une minute.", 503)
    if isinstance(exc, openai.APITimeoutError):
        return _unavailable("Le tuteur IA met trop de temps à répondre. Réessaie dans un instant.", 504)
    if isinstance(exc, openai.AuthenticationError):
        log.error("llm_auth_error")
        return _unavailable("Le tuteur IA est momentanément indisponible.", 503)
    log.warning("llm_error", error_type=exc.__class__.__name__)
    return _unavailable("Le tuteur IA a rencontré un problème. Réessaie dans un instant.", 502)


def fence_untrusted(text: str, label: str) -> str:
    """Encadre un texte non fiable (document importé, réponse d'élève).

    Les marqueurs ``<<<...>>>`` et les blocs de code éventuellement présents
    dans le texte sont neutralisés pour empêcher de « fermer » l'encadrement.
    Le prompt système doit préciser que ce contenu est une *donnée*, jamais une
    instruction.

    Args:
        text: Contenu non fiable.
        label: Nom de l'encadrement (ex. ``DOCUMENT``).

    Returns:
        Le texte encadré.
    """
    cleaned = _FENCE_RE.sub(" ", text)
    return f"<<<DEBUT {label}>>>\n{cleaned}\n<<<FIN {label}>>>"


async def complete_text(
    messages: list[Message],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    """Obtient une réponse texte complète.

    Args:
        messages: Messages au format OpenAI.
        max_tokens: Limite de tokens de sortie.
        temperature: Température d'échantillonnage.

    Returns:
        Le texte de la réponse.

    Raises:
        LLMError: En cas d'échec du fournisseur.
    """
    client = get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE if temperature is None else temperature,
        )
    except openai.OpenAIError as exc:
        raise _translate(exc) from exc
    return response.choices[0].message.content or ""


def parse_json_object(raw: str) -> dict[str, Any]:
    """Parse un objet JSON renvoyé par le modèle (tolère les blocs ```json).

    Args:
        raw: Texte brut du modèle.

    Returns:
        L'objet JSON décodé.

    Raises:
        ValueError: Si le texte n'est pas un objet JSON valide.
    """
    cleaned = _JSON_FENCE_RE.sub("", raw).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("JSON invalide") from exc
    if not isinstance(data, dict):
        raise ValueError("Un objet JSON est attendu")
    return data


async def complete_json(
    messages: list[Message],
    *,
    max_tokens: int = 900,
    temperature: float = 0.5,
) -> dict[str, Any]:
    """Obtient un objet JSON (mode JSON d'OpenAI), validé syntaxiquement.

    Args:
        messages: Messages au format OpenAI.
        max_tokens: Limite de tokens de sortie.
        temperature: Température d'échantillonnage.

    Returns:
        L'objet JSON décodé.

    Raises:
        LLMError: Échec du fournisseur, ou réponse non exploitable (502).
    """
    client = get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
    except openai.OpenAIError as exc:
        raise _translate(exc) from exc
    raw = response.choices[0].message.content or ""
    try:
        return parse_json_object(raw)
    except ValueError as exc:
        log.warning("llm_bad_json")
        raise _unavailable(
            "Le tuteur IA a produit une réponse inattendue. Réessaie dans un instant.", 502
        ) from exc


async def stream_text(messages: list[Message]) -> AsyncIterator[str]:
    """Diffuse la réponse du tuteur morceau par morceau.

    Args:
        messages: Messages au format OpenAI.

    Yields:
        Les fragments de texte successifs.

    Raises:
        LLMError: En cas d'échec du fournisseur (avant ou pendant le flux).
    """
    client = get_client()
    try:
        stream = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            if delta:
                yield delta
    except openai.OpenAIError as exc:
        raise _translate(exc) from exc
