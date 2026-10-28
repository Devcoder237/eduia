"""Table des signalements de réponses du tuteur.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.String(36)),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("excerpt", sa.String(600), nullable=False),
        sa.Column("comment", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_content_reports_created", "content_reports", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_content_reports_created", table_name="content_reports")
    op.drop_table("content_reports")
