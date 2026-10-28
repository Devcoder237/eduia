"""Envoi d'e-mails transactionnels (mot de passe oublié) par SMTP, sans dépendance supplémentaire.

Choix pour l'hébergement gratuit : le protocole SMTP standard fonctionne avec n'importe quel
fournisseur proposant une offre gratuite (Brevo, Gmail avec mot de passe d'application...).
Aucun secret dans le code : tout vient des variables d'environnement ``SMTP_*``.
Aucune adresse e-mail ni aucun lien n'est écrit dans les journaux de production.
"""

import smtplib
import ssl
from email.message import EmailMessage

import anyio

from app.core.config import settings
from app.core.i18n import Lang
from app.core.logging import get_logger

log = get_logger(__name__)

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


def _send_sync(message: EmailMessage) -> None:
    """Envoi bloquant (exécuté dans un thread) : STARTTLS (587) ou SSL direct (465)."""
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


async def send_password_reset_email(to_address: str, link: str, lang: Lang) -> bool:
    """Envoie le lien de réinitialisation. Ne lève jamais d'exception (tâche d'arrière-plan).

    Args:
        to_address: Adresse du destinataire.
        link: Lien complet vers la page de réinitialisation.
        lang: Langue de l'e-mail.

    Returns:
        ``True`` si l'e-mail a été remis au serveur SMTP, sinon ``False``.
    """
    if not smtp_configured():
        if settings.is_production:
            log.error("smtp_not_configured")
        else:
            # Développement/test uniquement : permet d'essayer le parcours sans fournisseur d'e-mail.
            log.warning("dev_reset_link", link=link)
        return False
    message = EmailMessage()
    message["Subject"] = _SUBJECT[lang]
    message["From"] = settings.SMTP_FROM or settings.SMTP_USER
    message["To"] = to_address
    message.set_content(build_reset_body(link, lang))
    try:
        await anyio.to_thread.run_sync(_send_sync, message)
    except (OSError, smtplib.SMTPException) as exc:
        log.error("reset_email_failed", error_type=exc.__class__.__name__)
        return False
    return True
