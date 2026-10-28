"""Chat avec le tuteur : sessions, messages (SSE), historique, import de documents.

Robustesse du streaming (correctif P0 de l'audit) : le message de l'élève est
enregistré AVANT l'appel à l'IA, et la réponse (même partielle) est enregistrée
dans un bloc ``finally`` protégé de l'annulation, avec une session de base de
données neuve — donc même si le client ferme l'onglet en plein flux, rien n'est
perdu.
"""

import json
from collections.abc import AsyncIterator

import anyio
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import llm
from app.core.config import settings
from app.core.deps import get_current_user_id
from app.core.i18n import Lang, get_lang, translate_detail
from app.core.logging import get_logger
from app.core.quota import consume_llm_quota
from app.core.rate_limit import enforce, llm_rate_limit
from app.core.security import enum_value
from app.core.timeutil import ensure_utc, utcnow
from app.db import database as dbmod
from app.db.database import get_db
from app.models.models import LearnerProfile, Message, PedagogyMode, SchoolLevel, Subject, TutorSession
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    LatestSessionOut,
    MessageOut,
    SessionCreate,
    SessionEndOut,
    SessionResponse,
    SessionSummary,
    UploadOut,
)
from app.services import tutor_service
from app.services.document_extract import SUPPORTED_EXTENSIONS, extract_text, get_extension
from app.services.tutor_service import LearnerContext

router = APIRouter()
log = get_logger(__name__)

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


async def _get_owned_session(db: AsyncSession, session_id: str, user_id: str) -> TutorSession:
    """Retourne la session si elle appartient à l'utilisateur (sinon 404)."""
    query = select(TutorSession).where(TutorSession.id == session_id, TutorSession.user_id == user_id)
    session = (await db.execute(query)).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session introuvable.")
    return session


async def _load_context(
    db: AsyncSession, session_id: str, user_id: str
) -> tuple[list[llm.Message], LearnerContext]:
    """Charge l'historique récent et le profil allégé de l'élève."""
    history_rows = await db.execute(
        select(Message.role, Message.content)
        .where(Message.session_id == session_id, Message.role != "system")
        .order_by(Message.created_at.desc())
        .limit(settings.MAX_CONVERSATION_HISTORY)
    )
    history: list[llm.Message] = [
        {"role": role, "content": content} for role, content in reversed(history_rows.all())
    ]

    profile = (
        await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user_id))
    ).scalar_one_or_none()
    context: LearnerContext = {
        "subject_scores": dict(profile.subject_scores or {}) if profile else {},
        "concept_mastery": dict(profile.concept_mastery or {}) if profile else {},
        "cognitive_style": (profile.cognitive_style if profile else None) or "mixte",
    }
    return history, context


async def _persist_assistant(session_id: str, content: str) -> None:
    """Enregistre la réponse du tuteur avec une session neuve, à l'abri de l'annulation."""
    if not content.strip():
        return
    with anyio.CancelScope(shield=True):
        try:
            async with dbmod.AsyncSessionLocal() as db:
                db.add(Message(session_id=session_id, role="assistant", content=content))
                await db.execute(
                    update(TutorSession)
                    .where(TutorSession.id == session_id)
                    .values(msg_count=TutorSession.msg_count + 1)
                )
                await db.commit()
        except Exception as exc:  # noqa: BLE001 - ne jamais masquer la fin du flux, mais journaliser
            log.error("stream_persist_failed", session_id=session_id, error_type=exc.__class__.__name__)


@router.post("/upload", response_model=UploadOut)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
) -> UploadOut:
    """Extrait le texte d'un document (PDF/Word/PowerPoint). Rien n'est stocké."""
    enforce(f"upload:user:{user_id}", 10, 60)
    ext = get_extension(file.filename)
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Format non supporté. Formats acceptés : PDF, Word (.docx), PowerPoint (.pptx).",
        )
    limit = settings.MAX_UPLOAD_BYTES
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(1024 * 256):
        size += len(chunk)
        if size > limit:
            raise HTTPException(
                status_code=413, detail=f"Fichier trop volumineux ({limit // (1024 * 1024)} Mo maximum)."
            )
        chunks.append(chunk)
    content = b"".join(chunks)

    filename = file.filename or f"document{ext}"
    result = await anyio.to_thread.run_sync(extract_text, filename, content)
    if result.error:
        raise HTTPException(status_code=422, detail=result.error)
    return UploadOut(
        filename=filename[:200], text=result.text, truncated=result.truncated, char_count=result.char_count
    )


@router.get("/session/latest", response_model=LatestSessionOut)
async def get_latest_session(
    subject: Subject = Query(...),
    level: SchoolLevel = Query(...),
    mode: PedagogyMode = Query(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> LatestSessionOut:
    """Retrouve la dernière session pour reprendre la conversation."""
    query = (
        select(TutorSession.id)
        .where(
            TutorSession.user_id == user_id,
            TutorSession.subject == subject,
            TutorSession.school_level == level,
            TutorSession.pedagogy_mode == mode,
        )
        .order_by(TutorSession.started_at.desc())
        .limit(1)
    )
    return LatestSessionOut(session_id=(await db.execute(query)).scalar_one_or_none())


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(
    subject: Subject | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[SessionSummary]:
    """Historique des conversations (une seule requête, sans N+1)."""
    preview = (
        select(Message.content)
        .where(Message.session_id == TutorSession.id, Message.role == "user")
        .order_by(Message.created_at.asc())
        .limit(1)
        .correlate(TutorSession)
        .scalar_subquery()
    )
    query = select(TutorSession, preview).where(TutorSession.user_id == user_id)
    if subject is not None:
        query = query.where(TutorSession.subject == subject)
    rows = (await db.execute(query.order_by(TutorSession.started_at.desc()).limit(100))).all()
    return [
        SessionSummary(
            session_id=s.id,
            subject=enum_value(s.subject),
            level=enum_value(s.school_level),
            mode=enum_value(s.pedagogy_mode),
            started_at=s.started_at,
            ended_at=s.ended_at,
            msg_count=s.msg_count or 0,
            preview=(first or "Conversation vide")[:90],
        )
        for s, first in rows
    ]


def _session_response(s: TutorSession) -> SessionResponse:
    return SessionResponse(
        session_id=s.id,
        subject=enum_value(s.subject),
        level=enum_value(s.school_level),
        mode=enum_value(s.pedagogy_mode),
        started_at=s.started_at,
    )


@router.get("/session/{session_id}/info", response_model=SessionResponse)
async def get_session_info(
    session_id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> SessionResponse:
    """Matière/niveau/mode d'une session (pour la rouvrir depuis l'historique)."""
    return _session_response(await _get_owned_session(db, session_id, user_id))


@router.post("/session", response_model=SessionResponse)
async def start_session(
    body: SessionCreate, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> SessionResponse:
    """Démarre une session de tutorat."""
    session = TutorSession(
        user_id=user_id, subject=body.subject, school_level=body.level, pedagogy_mode=body.mode
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_response(session)


@router.post("/message", response_model=ChatResponse, dependencies=[Depends(llm_rate_limit)])
async def send_message(
    body: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    lang: Lang = Depends(get_lang),
) -> ChatResponse:
    """Réponse complète du tuteur (sans streaming)."""
    session = await _get_owned_session(db, body.session_id, user_id)
    await consume_llm_quota(db, user_id)
    history, profile_ctx = await _load_context(db, session.id, user_id)
    messages = await tutor_service.build_messages(
        subject=enum_value(session.subject),
        level=enum_value(session.school_level),
        mode=enum_value(session.pedagogy_mode),
        message=body.message,
        history=history,
        learner_profile=profile_ctx,
        document_context=body.document_context,
        lang=lang,
    )
    reply = await tutor_service.full_reply(messages)

    db.add(Message(session_id=session.id, role="user", content=body.message))
    db.add(Message(session_id=session.id, role="assistant", content=reply))
    session.msg_count = (session.msg_count or 0) + 2
    await db.commit()
    return ChatResponse(
        session_id=session.id,
        message=reply,
        subject=enum_value(session.subject),
        level=enum_value(session.school_level),
        mode=enum_value(session.pedagogy_mode),
    )


def _sse(payload: dict[str, str]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/stream", dependencies=[Depends(llm_rate_limit)])
async def stream_message(
    body: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    lang: Lang = Depends(get_lang),
) -> StreamingResponse:
    """Réponse du tuteur en flux SSE (``data: {"text": ...}`` puis ``data: [DONE]``)."""
    session = await _get_owned_session(db, body.session_id, user_id)
    await consume_llm_quota(db, user_id)
    history, profile_ctx = await _load_context(db, session.id, user_id)
    session_id = str(session.id)
    messages = await tutor_service.build_messages(
        subject=enum_value(session.subject),
        level=enum_value(session.school_level),
        mode=enum_value(session.pedagogy_mode),
        message=body.message,
        history=history,
        learner_profile=profile_ctx,
        document_context=body.document_context,
        lang=lang,
    )

    # Le message de l'élève est sauvegardé d'abord : il survit à une déconnexion.
    db.add(Message(session_id=session_id, role="user", content=body.message))
    session.msg_count = (session.msg_count or 0) + 1
    await db.commit()

    async def event_generator() -> AsyncIterator[str]:
        parts: list[str] = []
        try:
            async for piece in tutor_service.stream_reply(messages):
                parts.append(piece)
                yield _sse({"text": piece})
            yield "data: [DONE]\n\n"
        except llm.LLMError as exc:
            yield _sse({"error": translate_detail(str(exc.detail), lang)})
            yield "data: [DONE]\n\n"
        finally:
            await _persist_assistant(session_id, "".join(parts))

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/history/{session_id}", response_model=list[MessageOut])
async def get_history(
    session_id: str, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> list[MessageOut]:
    """Messages d'une session."""
    await _get_owned_session(db, session_id, user_id)
    rows = await db.execute(
        select(Message)
        .where(Message.session_id == session_id, Message.role != "system")
        .order_by(Message.created_at.asc())
    )
    return [
        MessageOut(id=m.id, role=m.role, content=m.content, created_at=m.created_at)
        for m in rows.scalars().all()
    ]


@router.delete("/session/{session_id}", response_model=SessionEndOut)
async def end_session(
    session_id: str,
    satisfaction: int | None = Query(default=None, ge=1, le=5),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SessionEndOut:
    """Termine une session (idempotent : le compteur de sessions n'augmente qu'une fois)."""
    session = await _get_owned_session(db, session_id, user_id)
    if session.ended_at is None:
        now = utcnow()
        session.ended_at = now
        started = ensure_utc(session.started_at)
        session.duration_sec = int((now - started).total_seconds()) if started else 0
        profile = (
            await db.execute(select(LearnerProfile).where(LearnerProfile.user_id == user_id))
        ).scalar_one_or_none()
        if profile is not None:
            profile.total_sessions = (profile.total_sessions or 0) + 1
    if satisfaction is not None:
        session.satisfaction = satisfaction
    await db.commit()
    return SessionEndOut(status="session terminée", duration_sec=session.duration_sec or 0)
