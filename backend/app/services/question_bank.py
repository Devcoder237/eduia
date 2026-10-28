"""Banque de QCM validés : réutilisation entre élèves et statistiques d'item.

Pourquoi : (1) chaque question générée coûte 2 appels LLM (génération + vérification de la
clé) ; (2) l'étiquette de difficulté donnée par le modèle n'est pas fiable, alors que le taux
de réussite OBSERVÉ d'une question l'est (théorie classique des tests, « p-value » d'item).

Politique :
- une question n'est servie depuis la banque que si l'élève a au moins
  ``QUESTION_BANK_MIN_UNSEEN`` questions NON vues pour ce thème (sinon on génère : pas de
  répétition, et la banque se remplit) ;
- jamais deux fois la même question à un élève ;
- une question dont le taux de réussite reste sous le seuil après assez de réponses est
  marquée ``suspect`` et n'est plus servie (clé probablement fausse ou énoncé ambigu) ;
- plafond par thème (``QUESTION_BANK_MAX_PER_KEY``) pour borner la taille de la table.
"""

import hashlib
import random

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.i18n import Lang
from app.core.logging import get_logger
from app.models.models import QuestionBankItem, QuizAttempt, SchoolLevel, Subject
from app.services.quiz_service import GeneratedQuestion
from app.services.rag_service import normalize_text
from app.services.topics import canonical_topic

log = get_logger(__name__)

MIN_SERVED_FOR_DIFFICULTY = 10  # en dessous, le taux de réussite est trop bruité pour être affiché


def question_hash(question: str) -> str:
    """Empreinte d'une question (insensible à la casse, aux accents et aux espaces)."""
    normalized = " ".join(normalize_text(question).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def item_difficulty(item: QuestionBankItem) -> float | None:
    """Taux de réussite observé (0..1), ou ``None`` tant que l'échantillon est trop petit."""
    served = int(item.served or 0)
    if served < MIN_SERVED_FOR_DIFFICULTY:
        return None
    return round(int(item.correct or 0) / served, 3)


async def pick(
    db: AsyncSession, user_id: str, subject: Subject, level: SchoolLevel, topic: str, lang: Lang
) -> QuestionBankItem | None:
    """Choisit une question validée NON vue par l'élève, ou ``None`` (alors : générer)."""
    if not settings.QUESTION_BANK_ENABLED:
        return None
    seen = select(QuizAttempt.bank_id).where(QuizAttempt.user_id == user_id, QuizAttempt.bank_id.is_not(None))
    rows = await db.execute(
        select(QuestionBankItem)
        .where(
            QuestionBankItem.subject == subject,
            QuestionBankItem.school_level == level,
            QuestionBankItem.topic_key == canonical_topic(topic),
            QuestionBankItem.lang == lang,
            QuestionBankItem.suspect.is_(False),
            QuestionBankItem.id.not_in(seen),
        )
        .limit(settings.QUESTION_BANK_MAX_PER_KEY)
    )
    unseen = list(rows.scalars())
    if len(unseen) < settings.QUESTION_BANK_MIN_UNSEEN:
        return None
    return random.choice(unseen)  # noqa: S311 - tirage pédagogique, pas cryptographique


async def store(
    db: AsyncSession,
    subject: Subject,
    level: SchoolLevel,
    topic: str,
    lang: Lang,
    question: GeneratedQuestion,
) -> QuestionBankItem | None:
    """Ajoute une question validée à la banque (dédoublonnée, plafonnée par thème)."""
    if not settings.QUESTION_BANK_ENABLED:
        return None
    key = canonical_topic(topic)
    digest = question_hash(question.question)
    existing = (
        await db.execute(select(QuestionBankItem).where(QuestionBankItem.question_hash == digest))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    count = (
        await db.execute(
            select(func.count())
            .select_from(QuestionBankItem)
            .where(
                QuestionBankItem.subject == subject,
                QuestionBankItem.school_level == level,
                QuestionBankItem.topic_key == key,
                QuestionBankItem.lang == lang,
            )
        )
    ).scalar_one()
    if count >= settings.QUESTION_BANK_MAX_PER_KEY:
        return None
    item = QuestionBankItem(
        subject=subject,
        school_level=level,
        topic_key=key,
        lang=lang,
        question=question.question,
        question_hash=digest,
        options=question.options,
        correct_index=question.correct_index,
        explanation=question.explanation,
    )
    try:
        async with db.begin_nested():  # course possible entre deux requêtes : on retombe sur l'existante
            db.add(item)
            await db.flush()
    except IntegrityError:
        return (
            await db.execute(select(QuestionBankItem).where(QuestionBankItem.question_hash == digest))
        ).scalar_one_or_none()
    return item


async def record_outcome(db: AsyncSession, bank_id: str, is_correct: bool) -> None:
    """Met à jour les statistiques de l'item et l'écarte si son taux de réussite est aberrant."""
    await db.execute(
        update(QuestionBankItem)
        .where(QuestionBankItem.id == bank_id)
        .values(
            served=QuestionBankItem.served + 1, correct=QuestionBankItem.correct + (1 if is_correct else 0)
        )
    )
    item = await db.get(QuestionBankItem, bank_id)
    if item is None:
        return
    await db.refresh(item)
    served = int(item.served or 0)
    if (
        not item.suspect
        and served >= settings.QUESTION_BANK_SUSPECT_MIN_SERVED
        and int(item.correct or 0) / served < settings.QUESTION_BANK_SUSPECT_MAX_RATE
    ):
        item.suspect = True
        log.warning("question_bank_item_suspect", item_id=item.id, correct=item.correct, served=served)
