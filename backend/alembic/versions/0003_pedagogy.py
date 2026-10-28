"""Pédagogie : stabilité de mémoire, confiance au QCM, banque de questions.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "question_bank_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("subject", sa.String(32), nullable=False),
        sa.Column("school_level", sa.String(32), nullable=False),
        sa.Column("topic_key", sa.String(200), nullable=False),
        sa.Column("lang", sa.String(2), nullable=False, server_default="fr"),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("question_hash", sa.String(64), nullable=False),
        sa.Column("options", sa.JSON),
        sa.Column("correct_index", sa.Integer, nullable=False),
        sa.Column("explanation", sa.Text),
        sa.Column("served", sa.Integer, nullable=False, server_default="0"),
        sa.Column("correct", sa.Integer, nullable=False, server_default="0"),
        sa.Column("suspect", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("question_hash", name="uq_question_bank_hash"),
    )
    op.create_index(
        "ix_question_bank_lookup", "question_bank_items", ["subject", "school_level", "topic_key", "lang"]
    )
    with op.batch_alter_table("learner_profiles") as batch:
        batch.add_column(sa.Column("concept_stats", sa.JSON))
    with op.batch_alter_table("quiz_attempts") as batch:
        batch.add_column(sa.Column("confidence", sa.Integer))
        batch.add_column(sa.Column("bank_id", sa.String(36)))
        batch.create_foreign_key("fk_quiz_attempts_bank_id", "question_bank_items", ["bank_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("quiz_attempts") as batch:
        batch.drop_constraint("fk_quiz_attempts_bank_id", type_="foreignkey")
        batch.drop_column("bank_id")
        batch.drop_column("confidence")
    with op.batch_alter_table("learner_profiles") as batch:
        batch.drop_column("concept_stats")
    op.drop_index("ix_question_bank_lookup", table_name="question_bank_items")
    op.drop_table("question_bank_items")
