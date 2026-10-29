"""Modèles SQLAlchemy.

Choix de conception :
- Les Enum sont stockés en ``VARCHAR`` (valeurs, ex. « mathematiques »), pas en
  type Enum PostgreSQL natif : migrations plus simples et portables SQLite/PG.
- Tous les index et contraintes ont un nom explicite (migrations Alembic stables).
- Les datetimes sont UTC « aware » grâce à ``UTCDateTime``.
"""

import enum
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship

from app.core.timeutil import utcnow
from app.db.database import Base
from app.db.types import UTCDateTime


def new_uuid() -> str:
    """Génère un identifiant UUID4 sous forme de chaîne."""
    return str(uuid.uuid4())


class SchoolLevel(enum.StrEnum):
    """Niveau scolaire."""

    PRIMAIRE = "primaire"
    COLLEGE = "college"
    LYCEE = "lycee"
    UNIVERSITE = "universite"


class Subject(enum.StrEnum):
    """Matière."""

    MATHEMATIQUES = "mathematiques"
    PHYSIQUE = "physique"
    BIOLOGIE = "biologie"
    CHIMIE = "chimie"
    FRANCAIS = "francais"
    ANGLAIS = "anglais"
    HISTOIRE = "histoire"
    GEOGRAPHIE = "geographie"
    INFORMATIQUE = "informatique"


class PedagogyMode(enum.StrEnum):
    """Mode pédagogique du tuteur."""

    EXPLAIN = "explain"
    EXERCISE = "exercise"
    QUIZ = "quiz"
    SOCRATIC = "socratic"


class DifficultyLevel(enum.StrEnum):
    """Difficulté d'un exercice."""

    DEBUTANT = "debutant"
    INTERMEDIAIRE = "intermediaire"
    AVANCE = "avance"
    EXPERT = "expert"


def _enum(cls: type[enum.Enum]) -> SAEnum:
    """Colonne Enum stockée en VARCHAR (valeurs), validée à l'écriture."""
    return SAEnum(
        cls,
        values_callable=lambda e: [m.value for m in e],
        native_enum=False,
        length=32,
        create_constraint=False,
        validate_strings=True,
    )


class User(Base):
    """Compte utilisateur (élève, enseignant ou administrateur)."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("username", name="uq_users_username"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    email = Column(String(255), nullable=False)
    username = Column(String(100), nullable=False)
    hashed_pwd = Column(String(255), nullable=False)
    full_name = Column(String(200))
    is_active = Column(Boolean, nullable=False, default=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    is_admin = Column(Boolean, nullable=False, default=False)
    # Un enseignant ne voit QUE les élèves ayant rejoint une de SES classes.
    is_teacher = Column(Boolean, nullable=False, default=False)
    # Incrémenté pour révoquer tous les jetons (changement de mot de passe...).
    token_version = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(UTCDateTime, nullable=False, default=utcnow)
    updated_at = Column(UTCDateTime, nullable=False, default=utcnow, onupdate=utcnow)

    profile = relationship("LearnerProfile", back_populates="user", uselist=False)


class LearnerProfile(Base):
    """Profil adaptatif d'un apprenant (BKT, scores, séries)."""

    __tablename__ = "learner_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_learner_profiles_user_id"),)

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    school_level = Column(_enum(SchoolLevel), default=SchoolLevel.LYCEE)
    preferred_subjects = Column(JSON, default=list)
    cognitive_style = Column(String(50), default="mixte")
    avg_session_min = Column(Integer, default=30)
    total_questions = Column(Integer, default=0)
    total_sessions = Column(Integer, default=0)
    streak_days = Column(Integer, default=0)
    last_activity = Column(UTCDateTime)
    subject_scores = Column(JSON, default=dict)
    concept_mastery = Column(JSON, default=dict)
    # {"mathematiques": {"concept": "2026-06-20T10:00:00+00:00"}} : sert à l'oubli.
    concept_last_practiced = Column(JSON, default=dict)
    # {"mathematiques": {"concept": {"attempts": 4, "correct": 3, "stability": 60.0}}} :
    # stabilité de mémoire (oubli propre à chaque concept) et volume de preuves.
    concept_stats = Column(JSON, default=dict)
    pedagogy_prefs = Column(JSON, default=dict)
    created_at = Column(UTCDateTime, default=utcnow)
    updated_at = Column(UTCDateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="profile")


class TutorSession(Base):
    """Conversation avec le tuteur."""

    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_user_combo", "user_id", "subject", "school_level", "pedagogy_mode", "started_at"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    subject = Column(_enum(Subject), nullable=False)
    school_level = Column(_enum(SchoolLevel), nullable=False)
    pedagogy_mode = Column(_enum(PedagogyMode), default=PedagogyMode.EXPLAIN)
    started_at = Column(UTCDateTime, default=utcnow)
    ended_at = Column(UTCDateTime, nullable=True)
    duration_sec = Column(Integer, default=0)
    msg_count = Column(Integer, default=0)
    satisfaction = Column(Integer, nullable=True)
    topics_covered = Column(JSON, default=list)
    performance = Column(Float, nullable=True)
class ActivitySession(Base):
    """Session d'activité réelle d'un élève (temps d'utilisation mesuré, pas durée d'ouverture).

    Le navigateur envoie un signal de présence toutes les 30 s d'activité (onglet visible,
    interaction récente). Les signaux séparés de moins de 10 minutes alimentent la même session ;
    au-delà, une nouvelle session démarre. ``active_sec`` ne compte que le temps réellement actif.
    """

    __tablename__ = "activity_sessions"
    __table_args__ = (Index("ix_activity_sessions_user_last", "user_id", "last_beat_at"),)

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    started_at = Column(UTCDateTime, nullable=False, default=utcnow)
    last_beat_at = Column(UTCDateTime, nullable=False, default=utcnow)
    active_sec = Column(Integer, nullable=False, default=0)
    # {"tutor": 120, "quiz": 300, "exercise": 0, "exam": 0, "other": 15} : secondes actives par module.
    module_seconds = Column(JSON, default=dict)

class Message(Base):
    """Message d'une conversation (rôle ``user`` ou ``assistant``)."""

    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_session_created", "session_id", "created_at"),)

    id = Column(String(36), primary_key=True, default=new_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    tokens_used = Column(Integer, default=0)
    rag_used = Column(Boolean, default=False)
    created_at = Column(UTCDateTime, default=utcnow)


class Exercise(Base):
    """Exercice généré par l'IA, avec grille de correction."""

    __tablename__ = "exercises"
    __table_args__ = (Index("ix_exercises_lookup", "subject", "school_level", "topic", "created_at"),)

    id = Column(String(36), primary_key=True, default=new_uuid)
    subject = Column(_enum(Subject), nullable=False)
    school_level = Column(_enum(SchoolLevel), nullable=False)
    difficulty = Column(_enum(DifficultyLevel), nullable=False)
    topic = Column(String(200), nullable=False)
    statement = Column(Text, nullable=False)
    solution = Column(Text, nullable=False)
    hints = Column(JSON, default=list)
    concepts = Column(JSON, default=list)
    estimated_min = Column(Integer, default=10)
    # [{"critere": str, "points": float}], somme = 1.0.
    grading_rubric = Column(JSON, default=list)
    # Réponse numérique finale simple, sinon NULL (voir math_verify.py).
    numeric_answer = Column(String(100), nullable=True)
    created_at = Column(UTCDateTime, default=utcnow)


class ExerciseAttempt(Base):
    """Tentative d'un élève sur un exercice (une seule par élève et exercice)."""

    __tablename__ = "exercise_attempts"
    __table_args__ = (
        Index("ix_exercise_attempts_user_id", "user_id"),
        UniqueConstraint("user_id", "exercise_id", name="uq_exercise_attempts_user_exercise"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    exercise_id = Column(String(36), ForeignKey("exercises.id"), nullable=False)
    answer = Column(Text)
    score = Column(Float, nullable=True)
    feedback = Column(Text)
    hints_used = Column(Integer, default=0)
    time_sec = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    created_at = Column(UTCDateTime, default=utcnow)


class Badge(Base):
    """Définition d'un badge."""

    __tablename__ = "badges"
    __table_args__ = (UniqueConstraint("code", name="uq_badges_code"),)

    id = Column(String(36), primary_key=True, default=new_uuid)
    code = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    icon = Column(String(10))
    condition = Column(JSON)
    rarity = Column(String(20), default="common")


class UserBadge(Base):
    """Badge obtenu par un utilisateur (unique par couple)."""

    __tablename__ = "user_badges"
    __table_args__ = (
        UniqueConstraint("user_id", "badge_id", name="uq_user_badges_user_badge"),
        Index("ix_user_badges_user_id", "user_id"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    badge_id = Column(String(36), ForeignKey("badges.id"), nullable=False)
    earned_at = Column(UTCDateTime, default=utcnow)


class MasteryHistory(Base):
    """Historique de la maîtrise BKT d'un concept (un point par mise à jour)."""

    __tablename__ = "mastery_history"
    __table_args__ = (
        Index("ix_mastery_history_user_concept", "user_id", "subject", "concept", "recorded_at"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    subject = Column(String(50), nullable=False)
    concept = Column(String(200), nullable=False)
    score = Column(Float, nullable=False)
    recorded_at = Column(UTCDateTime, default=utcnow)


class Classroom(Base):
    """Classe gérée par un enseignant ; les élèves la rejoignent par code."""

    __tablename__ = "classrooms"
    __table_args__ = (
        UniqueConstraint("invite_code", name="uq_classrooms_invite_code"),
        Index("ix_classrooms_teacher_id", "teacher_id"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    teacher_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    name = Column(String(150), nullable=False)
    invite_code = Column(String(8), nullable=False)
    school_level = Column(_enum(SchoolLevel), default=SchoolLevel.LYCEE)
    is_active = Column(Boolean, default=True)
    created_at = Column(UTCDateTime, default=utcnow)


class ClassroomMembership(Base):
    """Lien élève ↔ classe, créé uniquement par l'élève (consentement)."""

    __tablename__ = "classroom_memberships"
    __table_args__ = (
        UniqueConstraint("classroom_id", "student_id", name="uq_membership_classroom_student"),
        Index("ix_classroom_memberships_student_id", "student_id"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    classroom_id = Column(String(36), ForeignKey("classrooms.id"), nullable=False)
    student_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    joined_at = Column(UTCDateTime, default=utcnow)


class ExamSession(Base):
    """Session d'examen blanc (chronométrée côté serveur)."""

    __tablename__ = "exam_sessions"
    __table_args__ = (Index("ix_exam_sessions_user_id", "user_id"),)

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    subject = Column(_enum(Subject), nullable=False)
    school_level = Column(_enum(SchoolLevel), nullable=False)
    exam_label = Column(String(100), default="BEPC")
    question_count = Column(Integer, default=10)
    duration_sec_planned = Column(Integer, default=600)
    started_at = Column(UTCDateTime, default=utcnow)
    ended_at = Column(UTCDateTime, nullable=True)
    duration_sec = Column(Integer, nullable=True)
    score = Column(Float, nullable=True)
    status = Column(String(20), default="in_progress")


class QuizAttempt(Base):
    """Question de quiz posée à un élève (et sa réponse)."""

    __tablename__ = "quiz_attempts"
    __table_args__ = (
        Index("ix_quiz_attempts_user_topic", "user_id", "subject", "topic"),
        # Unique : une seule question par position d'examen (NULL autorisés hors examen).
        Index("uq_quiz_attempts_exam_position", "exam_session_id", "exam_position", unique=True),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    subject = Column(_enum(Subject), nullable=False)
    school_level = Column(_enum(SchoolLevel), nullable=False)
    topic = Column(String(200), nullable=False)
    question = Column(Text, nullable=False)
    options = Column(JSON, default=list)
    correct_index = Column(Integer, nullable=False)
    answer_index = Column(Integer, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    explanation = Column(Text)
    justification = Column(Text, nullable=True)
    # Confiance déclarée AVANT la correction : 1 « je devine », 2 « plutôt sûr », 3 « sûr ».
    confidence = Column(Integer, nullable=True)
    # Question issue de la banque (NULL = générée spécialement pour cet élève).
    bank_id = Column(String(36), ForeignKey("question_bank_items.id"), nullable=True)
    exam_session_id = Column(String(36), ForeignKey("exam_sessions.id"), nullable=True)
    exam_position = Column(Integer, nullable=True)
    time_sec = Column(Integer, default=0)
    created_at = Column(UTCDateTime, default=utcnow)
    answered_at = Column(UTCDateTime, nullable=True)


class QuestionBankItem(Base):
    """QCM validé réutilisable entre élèves, avec ses statistiques d'item observées."""

    __tablename__ = "question_bank_items"
    __table_args__ = (
        UniqueConstraint("question_hash", name="uq_question_bank_hash"),
        Index("ix_question_bank_lookup", "subject", "school_level", "topic_key", "lang"),
    )

    id = Column(String(36), primary_key=True, default=new_uuid)
    subject = Column(_enum(Subject), nullable=False)
    school_level = Column(_enum(SchoolLevel), nullable=False)
    topic_key = Column(String(200), nullable=False)
    lang = Column(String(2), nullable=False, default="fr")
    question = Column(Text, nullable=False)
    question_hash = Column(String(64), nullable=False)
    options = Column(JSON, default=list)
    correct_index = Column(Integer, nullable=False)
    explanation = Column(Text)
    served = Column(Integer, nullable=False, default=0)
    correct = Column(Integer, nullable=False, default=0)
    # Écartée quand son taux de réussite est aberrant (clé probablement fausse / énoncé ambigu).
    suspect = Column(Boolean, nullable=False, default=False)
    created_at = Column(UTCDateTime, default=utcnow)


class StudyPlan(Base):
    """Planning de révision généré par l'IA."""

    __tablename__ = "study_plans"
    __table_args__ = (Index("ix_study_plans_user_id", "user_id"),)

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    exam_label = Column(String(200))
    target_date = Column(UTCDateTime, nullable=False)
    subjects = Column(JSON, default=list)
    school_level = Column(_enum(SchoolLevel), nullable=False)
    days = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    created_at = Column(UTCDateTime, default=utcnow)


class UsageCounter(Base):
    """Compteur d'usage quotidien par utilisateur (quota d'appels IA)."""

    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("user_id", "day", "kind", name="uq_usage_user_day_kind"),)

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    day = Column(Date, nullable=False)
    kind = Column(String(20), nullable=False)
    count = Column(Integer, nullable=False, default=0)


class ContentReport(Base):
    """Signalement d'une réponse du tuteur jugée fausse, inappropriée ou confuse.

    On ne stocke qu'un extrait court (jamais l'historique complet) et aucune donnée
    personnelle autre que l'identifiant de l'utilisateur (supprimé avec le compte).
    """

    __tablename__ = "content_reports"
    __table_args__ = (Index("ix_content_reports_created", "created_at"),)

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    session_id = Column(String(36), nullable=True)
    reason = Column(String(20), nullable=False)
    excerpt = Column(String(600), nullable=False)
    comment = Column(String(500), nullable=True)
    created_at = Column(UTCDateTime, nullable=False, default=utcnow)


class IdempotencyKey(Base):
    """Clé d'idempotence : un même (utilisateur, portée, clé) ne crée qu'une ressource."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("user_id", "scope", "key", name="uq_idempotency_user_scope_key"),)

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    scope = Column(String(30), nullable=False)
    key = Column(String(64), nullable=False)
    # NULL tant que la ressource n'est pas créée (requête « en cours »).
    resource_id = Column(String(36), nullable=True)
    created_at = Column(UTCDateTime, nullable=False, default=utcnow)


__all__ = [
    "Badge",
    "Classroom",
    "ContentReport",
    "ClassroomMembership",
    "DifficultyLevel",
    "ExamSession",
    "Exercise",
    "ExerciseAttempt",
    "IdempotencyKey",
    "LearnerProfile",
    "MasteryHistory",
    "Message",
    "PedagogyMode",
    "QuizAttempt",
    "SchoolLevel",
    "StudyPlan",
    "Subject",
    "TutorSession",
    "UsageCounter",
    "User",
    "UserBadge",
]
