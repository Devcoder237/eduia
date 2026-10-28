"""Exporte les réponses des élèves au format attendu par pyBKT, pour CALIBRER le BKT.

Les paramètres actuels (``MasteryTracker``) viennent de la littérature, pas des élèves
camerounais. Dès que quelques centaines de réponses réelles existent, ce script produit un CSV
(une ligne par réponse, ordre chronologique) à passer à pyBKT (ajustement EM de P_INIT, P_LEARN,
P_GUESS, P_SLIP par compétence).

Usage (depuis ``backend/``, avec DATABASE_URL et SECRET_KEY définis) ::

    python -m scripts.export_bkt_data --out bkt_export.csv

Confidentialité : l'identité des élèves est remplacée par une empreinte salée (``--salt`` ou
variable ``EXPORT_SALT``) ; aucun e-mail, nom ni texte de réponse n'est exporté. Sans sel,
l'empreinte serait devinable : un sel est donc OBLIGATOIRE.

Colonnes : order_id, user_id, skill_name, correct, item_type, hints_used, confidence, answered_at.
Étape suivante (sur votre machine, pas sur le serveur) ::

    pip install pyBKT
    python -c "from pyBKT.models import Model; m = Model(seed=42); m.fit(data_path='bkt_export.csv', \
skills='skill_name'); print(m.params())"
"""

import argparse
import asyncio
import csv
import hashlib
import os
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.security import enum_value
from app.db import database as dbmod
from app.models.models import Exercise, ExerciseAttempt, QuizAttempt
from app.services.topics import canonical_topic

FIELDS = [
    "order_id",
    "user_id",
    "skill_name",
    "correct",
    "item_type",
    "hints_used",
    "confidence",
    "answered_at",
]


def _anon(user_id: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()[:16]


async def collect(salt: str) -> list[dict[str, object]]:
    """Réponses QCM (hors examens) et exercices corrigés, triées par date."""
    rows: list[dict[str, object]] = []
    async with dbmod.AsyncSessionLocal() as db:
        quiz = await db.execute(
            select(QuizAttempt).where(
                QuizAttempt.answer_index.is_not(None), QuizAttempt.exam_session_id.is_(None)
            )
        )
        for q in quiz.scalars():
            rows.append(
                {
                    "user_id": _anon(str(q.user_id), salt),
                    "skill_name": f"{enum_value(q.subject)}|{canonical_topic(str(q.topic))}",
                    "correct": 1 if q.is_correct else 0,
                    "item_type": "mcq",
                    "hints_used": 0,
                    "confidence": q.confidence if q.confidence is not None else "",
                    "answered_at": (q.answered_at or q.created_at).isoformat(),
                }
            )
        ex = await db.execute(
            select(ExerciseAttempt, Exercise)
            .join(Exercise, Exercise.id == ExerciseAttempt.exercise_id)
            .where(ExerciseAttempt.completed.is_(True), ExerciseAttempt.score.is_not(None))
        )
        for attempt, exercise in ex.all():
            concepts = list(exercise.concepts or [exercise.topic])
            rows.append(
                {
                    "user_id": _anon(str(attempt.user_id), salt),
                    "skill_name": f"{enum_value(exercise.subject)}|{canonical_topic(str(concepts[0]))}",
                    "correct": 1 if float(attempt.score or 0) >= 0.8 else 0,
                    "item_type": "open",
                    "hints_used": int(attempt.hints_used or 0),
                    "confidence": "",
                    "answered_at": attempt.created_at.isoformat(),
                }
            )
    rows.sort(key=lambda r: str(r["answered_at"]))
    for order, row in enumerate(rows, start=1):
        row["order_id"] = order
    return rows


async def main(out: Path, salt: str) -> int:
    rows = await collect(salt)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    await dbmod.engine.dispose()
    print(f"{len(rows)} réponses exportées vers {out}")  # noqa: T201 - sortie CLI
    if len(rows) < 300:
        print("Attention : moins de 300 réponses, un ajustement EM serait peu fiable.")  # noqa: T201
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", type=Path, default=Path("bkt_export.csv"))
    parser.add_argument("--salt", default=os.environ.get("EXPORT_SALT", ""))
    args = parser.parse_args()
    if len(args.salt) < 8:
        sys.exit("Un sel d'au moins 8 caractères est obligatoire (--salt ou EXPORT_SALT).")
    sys.exit(asyncio.run(main(args.out, args.salt)))
