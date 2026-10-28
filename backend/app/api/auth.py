"""Authentification : inscription, connexion, refresh, mot de passe, suppression de compte."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.i18n import Lang, get_lang, translate_detail
from app.core.logging import get_logger
from app.core.rate_limit import client_ip, enforce, hash_key, ip_rate_limit
from app.core.security import (
    TokenType,
    create_reset_token,
    create_token,
    decode_reset_token,
    decode_token,
    hash_password,
    password_fingerprint,
    verify_password,
)
from app.db.database import get_db
from app.models.models import LearnerProfile, User
from app.schemas.chat import (
    DeleteAccountRequest,
    ForgotPasswordRequest,
    PasswordChange,
    PasswordChangedOut,
    RefreshRequest,
    ResetPasswordRequest,
    StatusOut,
    TokenResponse,
    UserLogin,
    UserOut,
    UserRegister,
)
from app.services.account_service import delete_account
from app.services.email_service import send_password_reset_email

router = APIRouter()
log = get_logger(__name__)

_register_limit = ip_rate_limit("register", lambda: settings.RL_REGISTER_PER_HOUR, 3600)

_INVALID_CREDENTIALS = "Email ou mot de passe incorrect."


def issue_tokens(user: User) -> TokenResponse:
    """Crée la paire access/refresh d'un utilisateur."""
    version = int(user.token_version or 0)
    access, expires_in = create_token(str(user.id), version, TokenType.ACCESS)
    refresh, _ = create_token(str(user.id), version, TokenType.REFRESH)
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=expires_in)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    body: UserRegister,
    _: None = Depends(_register_limit),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Crée un compte élève (jamais admin ni enseignant : rôles attribués par script)."""
    email = body.email.lower()
    if (await db.execute(select(User.id).where(User.email == email))).first():
        raise HTTPException(status_code=409, detail="Cet email est déjà utilisé.")
    if (await db.execute(select(User.id).where(User.username == body.username))).first():
        raise HTTPException(status_code=409, detail="Ce nom d'utilisateur est déjà pris.")

    user = User(
        email=email,
        username=body.username,
        hashed_pwd=hash_password(body.password),
        full_name=body.full_name,
        is_verified=False,
    )
    db.add(user)
    try:
        await db.flush()
        db.add(LearnerProfile(user_id=user.id))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Cet email ou ce nom d'utilisateur existe déjà."
        ) from None
    await db.refresh(user)
    log.info("user_registered", user_id=user.id)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, request: Request, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Connecte un utilisateur (limité par IP et par email contre le brute force)."""
    email = body.email.lower()
    enforce(f"login:ip:{client_ip(request)}", settings.RL_AUTH_PER_MIN, 60)
    enforce(f"login:email:{hash_key(email)}", settings.RL_AUTH_PER_MIN, 300)

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    password_ok = verify_password(body.password, user.hashed_pwd if user else None)
    if user is None or not password_ok:
        raise HTTPException(status_code=401, detail=_INVALID_CREDENTIALS)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Ce compte est désactivé.")
    return issue_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """Échange un refresh token valide contre de nouveaux jetons."""
    enforce(f"refresh:ip:{client_ip(request)}", settings.RL_AUTH_PER_MIN * 3, 60)
    payload = decode_token(body.refresh_token, TokenType.REFRESH)
    user = await db.get(User, payload["sub"])
    if user is None or not user.is_active or int(user.token_version or 0) != int(payload.get("tv", -1)):
        raise HTTPException(status_code=401, detail="Ta session a expiré. Reconnecte-toi, s'il te plaît.")
    return issue_tokens(user)


@router.get("/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)) -> User:
    """Retourne le profil de l'utilisateur connecté."""
    return user


@router.get("/verify")
async def verify_token(user: User = Depends(get_current_user)) -> dict[str, object]:
    """Vérifie que le jeton est valide."""
    return {"valid": True, "user_id": user.id}


@router.put("/password", response_model=PasswordChangedOut)
async def change_password(
    body: PasswordChange,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PasswordChangedOut:
    """Change le mot de passe et révoque tous les anciens jetons."""
    if not verify_password(body.current_password, user.hashed_pwd):
        raise HTTPException(status_code=400, detail="Le mot de passe actuel est incorrect.")
    user.hashed_pwd = hash_password(body.new_password)
    user.token_version = int(user.token_version or 0) + 1
    await db.commit()
    log.info("password_changed", user_id=user.id)
    return PasswordChangedOut(status="Mot de passe mis à jour avec succès.", tokens=issue_tokens(user))


@router.post("/forgot-password", response_model=StatusOut)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    lang: Lang = Depends(get_lang),
) -> StatusOut:
    """Envoie un lien de réinitialisation par e-mail.

    La réponse est IDENTIQUE que le compte existe ou non (pas d'énumération de comptes), et
    l'envoi se fait en arrière-plan (le temps de réponse ne révèle rien non plus). Limité par IP
    et par adresse pour éviter le harcèlement d'une boîte e-mail.
    """
    email = body.email.lower()
    enforce(f"forgot:ip:{client_ip(request)}", settings.RL_RESET_PER_HOUR * 2, 3600)
    enforce(f"forgot:email:{hash_key(email)}", settings.RL_RESET_PER_HOUR, 3600)
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is not None and user.is_active:
        token = create_reset_token(str(user.id), int(user.token_version or 0), user.hashed_pwd)
        link = f"{settings.FRONTEND_URL.rstrip('/')}/#/reset?token={token}"
        background.add_task(send_password_reset_email, user.email, link, lang)
        log.info("password_reset_requested", user_id=user.id)
    return StatusOut(
        status=translate_detail(
            "Si un compte existe avec cet e-mail, un lien de réinitialisation vient d'être envoyé.", lang
        )
    )


@router.post("/reset-password", response_model=StatusOut)
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    lang: Lang = Depends(get_lang),
) -> StatusOut:
    """Choisit un nouveau mot de passe grâce au lien reçu par e-mail.

    Le lien ne sert qu'une fois (il dépend du hash actuel), expire vite, et la réinitialisation
    révoque tous les jetons de connexion existants.
    """
    enforce(f"reset:ip:{client_ip(request)}", settings.RL_AUTH_PER_MIN, 60)
    payload = decode_reset_token(body.token)
    user = await db.get(User, payload["sub"])
    if (
        user is None
        or not user.is_active
        or int(user.token_version or 0) != int(payload.get("tv", -1))
        or payload.get("pwd") != password_fingerprint(user.hashed_pwd)
    ):
        raise HTTPException(
            status_code=400, detail="Ce lien est invalide ou a expiré. Demande un nouveau lien."
        )
    user.hashed_pwd = hash_password(body.new_password)
    user.token_version = int(user.token_version or 0) + 1
    await db.commit()
    log.info("password_reset_done", user_id=user.id)
    return StatusOut(
        status=translate_detail(
            "Mot de passe réinitialisé. Connecte-toi avec ton nouveau mot de passe.", lang
        )
    )


@router.post("/logout-all", response_model=StatusOut)
async def logout_all(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> StatusOut:
    """Déconnecte tous les appareils (révoque access et refresh tokens)."""
    user.token_version = int(user.token_version or 0) + 1
    await db.commit()
    return StatusOut(status="Tous tes appareils ont été déconnectés.")


@router.delete("/me", response_model=StatusOut)
async def delete_me(
    body: DeleteAccountRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StatusOut:
    """Supprime définitivement le compte et toutes les données associées (RGPD)."""
    if not verify_password(body.password, user.hashed_pwd):
        raise HTTPException(status_code=400, detail="Le mot de passe est incorrect.")
    user_id = str(user.id)
    await delete_account(db, user_id)
    await db.commit()
    log.info("account_deleted", user_id=user_id)
    return StatusOut(status="Ton compte et toutes tes données ont été supprimés.")
