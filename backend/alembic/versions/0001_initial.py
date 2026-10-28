"""Schéma initial EduIA (toutes les tables, index et contraintes nommés).

Revision ID: 0001
Revises:
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _ts(name: str, nullable: bool = True) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _fk(name: str, target: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey(target), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "users",
        _id(),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("hashed_pwd", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(200)),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("is_verified", sa.Boolean, nullable=False),
        sa.Column("is_admin", sa.Boolean, nullable=False),
        sa.Column("is_teacher", sa.Boolean, nullable=False),
        sa.Column("token_version", sa.Integer, nullable=False, server_default="0"),
        _ts("created_at", nullable=False),
        _ts("updated_at", nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )

    op.create_table(
        "learner_profiles",
        _id(),
        _fk("user_id", "users.id"),
        sa.Column("school_level", sa.String(32)),
        sa.Column("preferred_subjects", sa.JSON),
        sa.Column("cognitive_style", sa.String(50)),
        sa.Column("avg_session_min", sa.Integer),
        sa.Column("total_questions", sa.Integer),
        sa.Column("total_sessions", sa.Integer),
        sa.Column("streak_days", sa.Integer),
        _ts("last_activity"),
        sa.Column("subject_scores", sa.JSON),
        sa.Column("concept_mastery", sa.JSON),
        sa.Column("concept_last_practiced", sa.JSON),
        sa.Column("pedagogy_prefs", sa.JSON),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("user_id", name="uq_learner_profiles_user_id"),
    )

    op.create_table(
        "sessions",
        _id(),
        _fk("user_id", "users.id"),
        sa.Column("subject", sa.String(32), nullable=False),
        sa.Column("school_level", sa.String(32), nullable=False),
        sa.Column("pedagogy_mode", sa.String(32)),
        _ts("started_at"),
        _ts("ended_at"),
        sa.Column("duration_sec", sa.Integer),
        sa.Column("msg_count", sa.Integer),
        sa.Column("satisfaction", sa.Integer),
        sa.Column("topics_covered", sa.JSON),
        sa.Column("performance", sa.Float),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index(
        "ix_sessions_user_combo",
        "sessions",
        ["user_id", "subject", "school_level", "pedagogy_mode", "started_at"],
    )

    op.create_table(
        "messages",
        _id(),
        _fk("session_id", "sessions.id"),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tokens_used", sa.Integer),
        sa.Column("rag_used", sa.Boolean),
        _ts("created_at"),
    )
    op.create_index("ix_messages_session_created", "messages", ["session_id", "created_at"])

    op.create_table(
        "exercises",
        _id(),
        sa.Column("subject", sa.String(32), nullable=False),
        sa.Column("school_level", sa.String(32), nullable=False),
        sa.Column("difficulty", sa.String(32), nullable=False),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("statement", sa.Text, nullable=False),
        sa.Column("solution", sa.Text, nullable=False),
        sa.Column("hints", sa.JSON),
        sa.Column("concepts", sa.JSON),
        sa.Column("estimated_min", sa.Integer),
        sa.Column("grading_rubric", sa.JSON),
        sa.Column("numeric_answer", sa.String(100)),
        _ts("created_at"),
    )
    op.create_index("ix_exercises_lookup", "exercises", ["subject", "school_level", "topic", "created_at"])

    op.create_table(
        "exercise_attempts",
        _id(),
        _fk("user_id", "users.id"),
        _fk("exercise_id", "exercises.id"),
        sa.Column("answer", sa.Text),
        sa.Column("score", sa.Float),
        sa.Column("feedback", sa.Text),
        sa.Column("hints_used", sa.Integer),
        sa.Column("time_sec", sa.Integer),
        sa.Column("completed", sa.Boolean),
        _ts("created_at"),
        sa.UniqueConstraint("user_id", "exercise_id", name="uq_exercise_attempts_user_exercise"),
    )
    op.create_index("ix_exercise_attempts_user_id", "exercise_attempts", ["user_id"])

    op.create_table(
        "badges",
        _id(),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("icon", sa.String(10)),
        sa.Column("condition", sa.JSON),
        sa.Column("rarity", sa.String(20)),
        sa.UniqueConstraint("code", name="uq_badges_code"),
    )

    op.create_table(
        "user_badges",
        _id(),
        _fk("user_id", "users.id"),
        _fk("badge_id", "badges.id"),
        _ts("earned_at"),
        sa.UniqueConstraint("user_id", "badge_id", name="uq_user_badges_user_badge"),
    )
    op.create_index("ix_user_badges_user_id", "user_badges", ["user_id"])

    op.create_table(
        "mastery_history",
        _id(),
        _fk("user_id", "users.id"),
        sa.Column("subject", sa.String(50), nullable=False),
        sa.Column("concept", sa.String(200), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        _ts("recorded_at"),
    )
    op.create_index(
        "ix_mastery_history_user_concept",
        "mastery_history",
        ["user_id", "subject", "concept", "recorded_at"],
    )

    op.create_table(
        "classrooms",
        _id(),
        _fk("teacher_id", "users.id"),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("invite_code", sa.String(8), nullable=False),
        sa.Column("school_level", sa.String(32)),
        sa.Column("is_active", sa.Boolean),
        _ts("created_at"),
        sa.UniqueConstraint("invite_code", name="uq_classrooms_invite_code"),
    )
    op.create_index("ix_classrooms_teacher_id", "classrooms", ["teacher_id"])

    op.create_table(
        "classroom_memberships",
        _id(),
        _fk("classroom_id", "classrooms.id"),
        _fk("student_id", "users.id"),
        _ts("joined_at"),
        sa.UniqueConstraint("classroom_id", "student_id", name="uq_membership_classroom_student"),
    )
    op.create_index("ix_classroom_memberships_student_id", "classroom_memberships", ["student_id"])

    op.create_table(
        "exam_sessions",
        _id(),
        _fk("user_id", "users.id"),
        sa.Column("subject", sa.String(32), nullable=False),
        sa.Column("school_level", sa.String(32), nullable=False),
        sa.Column("exam_label", sa.String(100)),
        sa.Column("question_count", sa.Integer),
        sa.Column("duration_sec_planned", sa.Integer),
        _ts("started_at"),
        _ts("ended_at"),
        sa.Column("duration_sec", sa.Integer),
        sa.Column("score", sa.Float),
        sa.Column("status", sa.String(20)),
    )
    op.create_index("ix_exam_sessions_user_id", "exam_sessions", ["user_id"])

    op.create_table(
        "quiz_attempts",
        _id(),
        _fk("user_id", "users.id"),
        sa.Column("subject", sa.String(32), nullable=False),
        sa.Column("school_level", sa.String(32), nullable=False),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("options", sa.JSON),
        sa.Column("correct_index", sa.Integer, nullable=False),
        sa.Column("answer_index", sa.Integer),
        sa.Column("is_correct", sa.Boolean),
        sa.Column("explanation", sa.Text),
        sa.Column("justification", sa.Text),
        _fk("exam_session_id", "exam_sessions.id", nullable=True),
        sa.Column("exam_position", sa.Integer),
        sa.Column("time_sec", sa.Integer),
        _ts("created_at"),
        _ts("answered_at"),
    )
    op.create_index("ix_quiz_attempts_user_topic", "quiz_attempts", ["user_id", "subject", "topic"])
    op.create_index(
        "uq_quiz_attempts_exam_position",
        "quiz_attempts",
        ["exam_session_id", "exam_position"],
        unique=True,
    )

    op.create_table(
        "study_plans",
        _id(),
        _fk("user_id", "users.id"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("exam_label", sa.String(200)),
        _ts("target_date", nullable=False),
        sa.Column("subjects", sa.JSON),
        sa.Column("school_level", sa.String(32), nullable=False),
        sa.Column("days", sa.JSON),
        sa.Column("is_active", sa.Boolean),
        _ts("created_at"),
    )
    op.create_index("ix_study_plans_user_id", "study_plans", ["user_id"])

    op.create_table(
        "usage_counters",
        _id(),
        _fk("user_id", "users.id"),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("count", sa.Integer, nullable=False),
        sa.UniqueConstraint("user_id", "day", "kind", name="uq_usage_user_day_kind"),
    )

    op.create_table(
        "idempotency_keys",
        _id(),
        _fk("user_id", "users.id"),
        sa.Column("scope", sa.String(30), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(36)),
        _ts("created_at", nullable=False),
        sa.UniqueConstraint("user_id", "scope", "key", name="uq_idempotency_user_scope_key"),
    )


def downgrade() -> None:
    for table in (
        "idempotency_keys",
        "usage_counters",
        "study_plans",
        "quiz_attempts",
        "exam_sessions",
        "classroom_memberships",
        "classrooms",
        "mastery_history",
        "user_badges",
        "badges",
        "exercise_attempts",
        "exercises",
        "messages",
        "sessions",
        "learner_profiles",
        "users",
    ):
        op.drop_table(table)
