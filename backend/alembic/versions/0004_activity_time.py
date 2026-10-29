"""Temps d'activité réel : sessions mesurées par signaux de présence.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "activity_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_beat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_sec", sa.Integer, nullable=False, server_default="0"),
        sa.Column("module_seconds", sa.JSON),
    )
    op.create_index("ix_activity_sessions_user_last", "activity_sessions", ["user_id", "last_beat_at"])


def downgrade() -> None:
    op.drop_index("ix_activity_sessions_user_last", table_name="activity_sessions")
    op.drop_table("activity_sessions")