"""Point d'entrée FastAPI d'EduIA.

Décisions pour l'hébergement 100 % gratuit :
- ``/health`` ne touche PAS la base : UptimeRobot peut le pinguer toutes les
  14 min (contre l'endormissement de Render) sans maintenir Neon éveillé (le
  quota de calcul gratuit de Neon serait sinon consommé 24 h/24).
  ``/health/ready`` vérifie la base (usage manuel/CI).
- Le schéma est géré par Alembic (``alembic upgrade head`` au démarrage du
  conteneur), jamais par ``create_all`` en production.
- Un seul worker (512 Mo de RAM) : le limiteur de débit en mémoire reste exact.
"""

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api import (
    admin,
    auth,
    chat,
    classrooms,
    exams,
    exercises,
    progress,
    quiz,
    reports,
    study_plans,
)
from app.core.config import settings
from app.core.i18n import lang_of, translate_detail
from app.core.logging import configure_logging, get_logger
from app.db import database as dbmod
from app.services.badge_service import ensure_badges

configure_logging(settings.LOG_LEVEL, json_output=settings.is_production)
log = get_logger("eduia")

if settings.SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=settings.APP_VERSION,
        traces_sample_rate=0.0,
        send_default_pii=False,  # mineurs : aucune donnée personnelle envoyée
    )

SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"permissions-policy", b"camera=(), geolocation=(), payment=()"),
    (b"cross-origin-resource-policy", b"same-site"),
]
if settings.is_production:
    SECURITY_HEADERS.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))


class RequestContextMiddleware:
    """Middleware ASGI pur : identifiant de requête, en-têtes de sécurité, journal d'accès.

    Écrit en ASGI pur (et non ``BaseHTTPMiddleware``) pour ne pas perturber le
    streaming SSE ni la détection de déconnexion du client.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex[:12]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        status_holder = {"code": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                headers.extend(SECURITY_HEADERS)
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if scope["path"] not in ("/health", "/"):
                log.info(
                    "http_request",
                    method=scope["method"],
                    path=scope["path"],
                    status=status_holder["code"],
                    duration_ms=round((time.perf_counter() - started) * 1000, 1),
                )


class SelectiveGZipMiddleware(GZipMiddleware):
    """GZip qui laisse passer le flux SSE tel quel (la compression le mettrait en tampon)."""

    EXCLUDED_PATHS = ("/api/chat/stream",)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] in self.EXCLUDED_PATHS:
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Démarrage : crée les badges manquants (idempotent). Le schéma vient d'Alembic."""
    log.info("startup", environment=settings.ENVIRONMENT, version=settings.APP_VERSION)
    try:
        async with dbmod.AsyncSessionLocal() as session:
            created = await ensure_badges(session)
            if created:
                log.info("badges_created", count=created)
    except Exception as exc:  # noqa: BLE001 - l'API doit démarrer même si la base est momentanément injoignable
        log.error("startup_db_unavailable", error_type=exc.__class__.__name__)
    yield
    await dbmod.engine.dispose()
    log.info("shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    description="API du tuteur IA adaptatif EduIA.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(SelectiveGZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,  # authentification par en-tête Bearer, pas de cookies
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept-Language"],
    expose_headers=["X-Request-ID", "Retry-After"],
    max_age=600,
)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Réponses d'erreur HTTP au format uniforme ``{"detail": ...}`` (message dans la langue demandée)."""
    detail = exc.detail
    if isinstance(detail, str):
        detail = translate_detail(detail, lang_of(request))
    return JSONResponse(
        status_code=exc.status_code, content={"detail": detail}, headers=getattr(exc, "headers", None)
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Erreur de validation : message lisible, sans renvoyer les valeurs saisies."""
    fields = [".".join(str(p) for p in err["loc"] if p != "body") for err in exc.errors()]
    first = exc.errors()[0].get("msg", "Données invalides.") if exc.errors() else "Données invalides."
    detail = translate_detail(first.removeprefix("Value error, "), lang_of(request))
    return JSONResponse(status_code=422, content={"detail": detail, "fields": fields})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Dernier filet : journalise (sans données perso) et répond poliment."""
    log.error("unhandled_exception", error_type=exc.__class__.__name__, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": translate_detail(
                "Oups, une erreur est survenue de notre côté. Réessaie dans un instant.", lang_of(request)
            )
        },
    )


app.include_router(auth.router, prefix="/api/auth", tags=["Authentification"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat Tuteur"])
app.include_router(progress.router, prefix="/api/progress", tags=["Progression"])
app.include_router(exercises.router, prefix="/api/exercises", tags=["Exercices"])
app.include_router(quiz.router, prefix="/api/quiz", tags=["Quiz"])
app.include_router(study_plans.router, prefix="/api/study-plans", tags=["Plans d'étude"])
app.include_router(exams.router, prefix="/api/exams", tags=["Examen blanc"])
app.include_router(admin.router, prefix="/api/admin", tags=["Administration"])
app.include_router(reports.router, prefix="/api/reports", tags=["Signalements"])
app.include_router(classrooms.router, prefix="/api/classrooms", tags=["Mode enseignant"])


@app.get("/", tags=["Health"])
async def root() -> dict[str, str]:
    """Identité du service."""
    return {"status": "ok", "service": "EduIA Backend", "version": settings.APP_VERSION}


@app.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    """Liveness sans accès à la base (cible du ping UptimeRobot)."""
    return {"status": "healthy"}


@app.get("/health/ready", tags=["Health"])
async def ready() -> JSONResponse:
    """Readiness : vérifie la connexion à la base de données."""
    try:
        async with dbmod.AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        log.error("readiness_failed", error_type=exc.__class__.__name__)
        return JSONResponse(status_code=503, content={"status": "database_unavailable"})
    return JSONResponse(content={"status": "ready"})
