"""Envoi d'e-mails transactionnels (mot de passe oublié).

Deux modes, choisis par les variables d'environnement (aucun secret dans le code) :

* API HTTPS Brevo (``EMAIL_API_KEY`` + ``EMAIL_FROM``) : à utiliser en production gratuite, car
  Render bloque les ports SMTP sortants sur son offre gratuite.
* SMTP (``SMTP_*``) : utile en local ou chez un hébergeur qui autorise le SMTP.

Aucune adresse e-mail ni aucun lien n'est écrit dans les journaux de production.
"""

import smtplib
import ssl
from email.message import EmailMessage

import anyio
import httpx

from app.core.config import settings
from app.core.i18n import Lang
from app.core.logging import get_logger

log = get_logger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"

_SUBJECT: dict[Lang, str] = {
    "fr": "EduIA — Réinitialisation de ton mot de passe",
    "en": "EduIA — Reset your password",
}


def build_reset_body(link: str, lang: Lang) -> str:
    """Texte de l'e-mail de réinitialisation (sans HTML : lisible partout, même en 3G)."""
    minutes = settings.RESET_TOKEN_EXPIRE_MINUTES
    if lang == "en":
        return (
            "Hello,\n\n"
            "We received a request to reset your EduIA password. "
            f"Open this link within {minutes} minutes to choose a new one:\n\n{link}\n\n"
            "If you did not ask for this, ignore this email: your password stays unchanged.\n\n"
            "The EduIA team\n"
        )
    return (
        "Bonjour,\n\n"
        "Nous avons reçu une demande de réinitialisation de ton mot de passe EduIA. "
        f"Ouvre ce lien dans les {minutes} minutes pour en choisir un nouveau :\n\n{link}\n\n"
        "Si tu n'es pas à l'origine de cette demande, ignore cet e-mail : ton mot de passe reste inchangé.\n\n"
        "L'équipe EduIA\n"
    )


def smtp_configured() -> bool:
    """Vrai si un serveur SMTP et un expéditeur sont configurés."""
    return bool(settings.SMTP_HOST and (settings.SMTP_FROM or settings.SMTP_USER))


def api_configured() -> bool:
    """Vrai si l'envoi par API HTTPS (Brevo) est configuré."""
    return bool(settings.EMAIL_API_KEY and settings.EMAIL_FROM)


def _send_sync(message: EmailMessage) -> None:
    """Envoi SMTP bloquant (exécuté dans un thread) : STARTTLS (587) ou SSL direct (465)."""
    context = ssl.create_default_context()
    if settings.SMTP_PORT == 465:
        with smtplib.SMTP_SSL(
            settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_S, context=context
        ) as server:
            _login_and_send(server, message)
        return
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_S) as server:
        server.starttls(context=context)
        _login_and_send(server, message)


def _login_and_send(server: smtplib.SMTP, message: EmailMessage) -> None:
    if settings.SMTP_USER:
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
    server.send_message(message)


async def _send_via_api(to_address: str, subject: str, body: str) -> None:
    """Envoie l'e-mail par l'API HTTPS de Brevo.

    Raises:
        httpx.HTTPError: Échec réseau, délai dépassé ou réponse d'erreur (clé ou expéditeur refusés).
    """
    payload = {
        "sender": {"name": settings.EMAIL_FROM_NAME, "email": settings.EMAIL_FROM},
        "to": [{"email": to_address}],
        "subject": subject,
        "textContent": body,
    }
    headers = {"api-key": settings.EMAIL_API_KEY, "accept": "application/json"}
    async with httpx.AsyncClient(timeout=settings.SMTP_TIMEOUT_S) as client:
        response = await client.post(BREVO_SEND_URL, json=payload, headers=headers)
        response.raise_for_status()


async def send_password_reset_email(to_address: str, link: str, lang: Lang) -> bool:
    """Envoie le lien de réinitialisation. Ne lève jamais d'exception (tâche d'arrière-plan).

    Args:
        to_address: Adresse du destinataire.
        link: Lien complet vers la page de réinitialisation.
        lang: Langue de l'e-mail.

    Returns:
        ``True`` si l'e-mail a été remis au fournisseur (API ou SMTP), sinon ``False``.
    """
    if not (api_configured() or smtp_configured()):
        if settings.is_production:
            log.error("email_not_configured")
        else:
            # Développement/test uniquement : permet d'essayer le parcours sans fournisseur d'e-mail.
            log.warning("dev_reset_link", link=link)
        return False
    subject = _SUBJECT[lang]
    body = build_reset_body(link, lang)
    try:
        if api_configured():
            await _send_via_api(to_address, subject, body)
        else:
            message = EmailMessage()
            message["Subject"] = subject
            message["From"] = settings.SMTP_FROM or settings.SMTP_USER
            message["To"] = to_address
            message.set_content(body)
            await anyio.to_thread.run_sync(_send_sync, message)
    except httpx.HTTPStatusError as exc:
        # Le code HTTP aide à diagnostiquer (401 clé invalide, 400/403 expéditeur non validé).
        log.error("reset_email_failed", error_type=exc.__class__.__name__, status=exc.response.status_code)
        return False
    except (httpx.HTTPError, OSError, smtplib.SMTPException) as exc:
        log.error("reset_email_failed", error_type=exc.__class__.__name__)
        return False
    return True