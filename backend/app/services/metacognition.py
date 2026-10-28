"""Calibration de la confiance : l'élève sait-il ce qu'il sait ?

La confiance (1 = « je devine », 2 = « plutôt sûr », 3 = « sûr ») est déclarée AVANT la
correction. Deux situations sont pédagogiquement utiles :
- erreur avec confiance 3 (« surconfiance ») : une idée fausse solidement ancrée, que la
  recherche sur l'hypercorrection montre justement très corrigeable si on la confronte ;
- réussite avec confiance 1 (« sous-confiance » / chance) : la maîtrise est probablement
  fragile, et la réussite compte moins comme preuve d'apprentissage (le BKT en tient compte).
"""

from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import QuizAttempt

Calibration = Literal["overconfident", "underconfident", "calibrated"]

MIN_SAMPLE = 10  # en dessous, un profil de calibration serait du bruit


def classify(confidence: int | None, correct: bool) -> Calibration | None:
    """Calibration d'UNE réponse, ou ``None`` si la confiance n'a pas été déclarée."""
    if confidence is None:
        return None
    if confidence == 3 and not correct:
        return "overconfident"
    if confidence == 1 and correct:
        return "underconfident"
    return "calibrated"


async def summary(db: AsyncSession, user_id: str) -> dict[str, object]:
    """Profil de calibration de l'élève (sur ses 200 dernières réponses avec confiance)."""
    rows = (
        await db.execute(
            select(QuizAttempt.confidence, QuizAttempt.is_correct)
            .where(
                QuizAttempt.user_id == user_id,
                QuizAttempt.confidence.is_not(None),
                QuizAttempt.is_correct.is_not(None),
            )
            .order_by(QuizAttempt.answered_at.desc())
            .limit(200)
        )
    ).all()
    n = len(rows)
    over = sum(1 for c, ok in rows if classify(c, bool(ok)) == "overconfident")
    under = sum(1 for c, ok in rows if classify(c, bool(ok)) == "underconfident")
    label: str | None = None
    if n >= MIN_SAMPLE:
        label = "overconfident" if over / n >= 0.2 else "underconfident" if under / n >= 0.2 else "calibrated"
    return {
        "answered": n,
        "overconfident_rate": round(over / n, 3) if n else 0.0,
        "underconfident_rate": round(under / n, 3) if n else 0.0,
        "label": label,
    }
