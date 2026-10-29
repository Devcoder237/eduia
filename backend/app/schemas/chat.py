"""Schémas Pydantic v2 (entrées validées strictement, sorties typées).

Décisions : matières, niveaux et modes sont des Enum (valeurs inconnues → 422),
tous les textes libres ont une longueur maximale, et les sorties n'utilisent ni
``Any`` ni ``dict`` non typé.
"""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.models import DifficultyLevel, PedagogyMode, SchoolLevel, Subject

PASSWORD_MAX_BYTES = 72
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _check_password_strength(value: str, label: str = "Le mot de passe") -> str:
    """Valide la robustesse minimale d'un mot de passe (bcrypt : 72 octets max)."""
    if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"{label} est trop long (72 octets maximum).")
    if not any(c.isupper() for c in value):
        raise ValueError(f"{label} doit contenir au moins une majuscule.")
    if not any(c.isdigit() for c in value):
        raise ValueError(f"{label} doit contenir au moins un chiffre.")
    return value


# ───────────────────────────── Authentification ─────────────────────────────


class UserRegister(BaseModel):
    """Inscription."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=72)
    full_name: str | None = Field(default=None, max_length=100)

    @field_validator("username")
    @classmethod
    def _username_chars(cls, value: str) -> str:
        if not _USERNAME_RE.match(value):
            raise ValueError(
                "Le nom d'utilisateur ne peut contenir que lettres, chiffres, « _ », « . » et « - »."
            )
        return value

    @field_validator("password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        return _check_password_strength(value)


class UserLogin(BaseModel):
    """Connexion."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class PasswordChange(BaseModel):
    """Changement de mot de passe."""

    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        return _check_password_strength(value, "Le nouveau mot de passe")


class ForgotPasswordRequest(BaseModel):
    """Demande de lien de réinitialisation (la réponse ne révèle jamais si l'e-mail existe)."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Nouveau mot de passe choisi via le lien reçu par e-mail."""

    token: str = Field(min_length=10, max_length=2000)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def _password_strength(cls, value: str) -> str:
        return _check_password_strength(value, "Le nouveau mot de passe")


class DeleteAccountRequest(BaseModel):
    """Suppression de compte (RGPD) : confirmée par le mot de passe."""

    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    """Échange d'un refresh token contre de nouveaux jetons."""

    refresh_token: str = Field(min_length=10, max_length=2000)


class TokenResponse(BaseModel):
    """Jetons renvoyés après connexion ou rafraîchissement."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - type de schéma OAuth, pas un secret
    expires_in: int


class PasswordChangedOut(BaseModel):
    """Mot de passe changé : les anciens jetons sont révoqués, de nouveaux sont fournis."""

    status: str
    tokens: TokenResponse


class UserOut(BaseModel):
    """Utilisateur (jamais de hash de mot de passe)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    username: str
    full_name: str | None
    is_active: bool
    is_admin: bool = False
    is_teacher: bool = False
    created_at: datetime


class ReportRequest(BaseModel):
    """Signalement d'une réponse du tuteur."""

    reason: Literal["wrong", "inappropriate", "confusing", "other"]
    excerpt: str = Field(min_length=1, max_length=600)
    session_id: str | None = Field(default=None, max_length=36)
    comment: str | None = Field(default=None, max_length=500)


class StatusOut(BaseModel):
    """Réponse simple « statut »."""

    status: str

class HeartbeatIn(BaseModel):
    """Signal de présence : secondes réellement actives écoulées depuis le signal précédent."""

    module: Literal["tutor", "quiz", "exercise", "exam", "other"]
    seconds: int = Field(ge=1, le=60)
# ───────────────────────────── Chat ─────────────────────────────


class SessionCreate(BaseModel):
    """Création d'une session de tutorat."""

    subject: Subject
    level: SchoolLevel
    mode: PedagogyMode = PedagogyMode.EXPLAIN


class SessionResponse(BaseModel):
    """Session de tutorat."""

    session_id: str
    subject: str
    level: str
    mode: str
    started_at: datetime


class LatestSessionOut(BaseModel):
    """Dernière session correspondant à une combinaison matière/niveau/mode."""

    session_id: str | None


class ChatRequest(BaseModel):
    """Message de l'élève.

    ``subject``/``level``/``mode`` sont conservés pour compatibilité mais le
    serveur utilise ceux de la session (source de vérité).
    """

    session_id: str = Field(min_length=1, max_length=36)
    message: str = Field(min_length=1, max_length=2000)
    subject: Subject
    level: SchoolLevel
    mode: PedagogyMode = PedagogyMode.EXPLAIN
    document_context: str | None = Field(default=None, max_length=8000)


class ChatResponse(BaseModel):
    """Réponse complète du tuteur (mode non-streaming)."""

    session_id: str
    message: str
    subject: str
    level: str
    mode: str


class MessageOut(BaseModel):
    """Message d'historique."""

    id: str
    role: str
    content: str
    created_at: datetime


class SessionSummary(BaseModel):
    """Résumé d'une conversation passée."""

    session_id: str
    subject: str
    level: str
    mode: str
    started_at: datetime
    ended_at: datetime | None
    msg_count: int
    preview: str


class SessionEndOut(BaseModel):
    """Résultat de la fin de session."""

    status: str
    duration_sec: int


class UploadOut(BaseModel):
    """Texte extrait d'un document importé (rien n'est stocké côté serveur)."""

    filename: str
    text: str
    truncated: bool
    char_count: int


# ───────────────────────────── Exercices ─────────────────────────────


class ExerciseRequest(BaseModel):
    """Demande de génération d'exercice."""

    subject: Subject
    level: SchoolLevel
    topic: str = Field(min_length=1, max_length=200)
    difficulty: DifficultyLevel | None = None
    # Clé d'idempotence : le même couple (utilisateur, clé) renvoie le même exercice.
    request_id: str | None = Field(default=None, min_length=8, max_length=64)


class ExerciseOut(BaseModel):
    """Exercice (sans la solution)."""

    id: str
    subject: str
    level: str
    difficulty: str
    topic: str
    statement: str
    hints: list[str]
    concepts: list[str]
    estimated_min: int


class AttemptSubmit(BaseModel):
    """Réponse de l'élève à un exercice."""

    exercise_id: str = Field(min_length=1, max_length=36)
    answer: str = Field(min_length=1, max_length=5000)
    # Indices affichés avant la réponse : une réussite aidée prouve moins (borné côté serveur).
    hints_used: int = Field(default=0, ge=0, le=10)


class RubricScoreItem(BaseModel):
    """Note d'un critère de la grille."""

    critere: str
    points_max: float
    points_obtenus: float
    taux: float
    justification: str


class AttemptResult(BaseModel):
    """Résultat de la correction."""

    exercise_id: str
    score: float
    correct: bool
    partial: bool
    feedback: str
    errors: list[str]
    concepts_to_review: list[str]
    positive_points: list[str]
    rubric_breakdown: list[RubricScoreItem] = Field(default_factory=list)


class GuidedReviewRequest(BaseModel):
    """Demande de plan de révision guidée."""

    subject: Subject | None = None


class GuidedReviewItem(BaseModel):
    """Élément de révision."""

    priority: str
    subject: str
    concept: str | None
    score: float
    reason: str
    action: str


class GuidedReviewPlan(BaseModel):
    """Plan de révision guidée."""

    items: list[GuidedReviewItem]
    has_gaps: bool


# ───────────────────────────── Progression ─────────────────────────────


class SubjectScore(BaseModel):
    """Score par matière."""

    subject: str
    score: float
    trend: str


class Recommendation(BaseModel):
    """Recommandation personnalisée."""

    priority: str
    subject: str
    concept: str | None
    score: float
    reason: str
    action: str


class BadgeOut(BaseModel):
    """Badge obtenu."""

    code: str
    name: str
    icon: str
    description: str
    rarity: str
    earned_at: datetime | None


class RecentSession(BaseModel):
    """Session récente (tableau de bord)."""

    id: str
    subject: str
    duration: int | None
    started_at: str


class HeatmapCell(BaseModel):
    """Case du calendrier d'activité."""

    date: str
    level: int


class ProgressDashboard(BaseModel):
    """Tableau de bord de l'élève."""

    total_sessions: int
    total_questions: int
    streak_days: int
    subject_scores: list[SubjectScore]
    recent_sessions: list[RecentSession]
    recommendations: list[Recommendation]
    badges: list[BadgeOut]
    heatmap: list[HeatmapCell]


class WeeklyStat(BaseModel):
    """Statistique hebdomadaire."""

    week_label: str
    questions: int
    avg_score: float


class DetailedStats(BaseModel):
    """Statistiques détaillées."""

    avg_session_min: float
    total_time_min: int
    weekly_progress: list[WeeklyStat]
    sessions_by_subject: dict[str, int]
    best_subject: str | None
    weakest_subject: str | None


class MasteryConceptOption(BaseModel):
    """Concept avec assez d'historique pour être tracé."""

    subject: str
    concept: str
    points_count: int
    latest_score: float


class MasteryHistoryPoint(BaseModel):
    """Point de la courbe de maîtrise."""

    recorded_at: datetime
    score: float


# ───────────────────────────── Quiz ─────────────────────────────


class QuizQuestion(BaseModel):
    """Question de quiz (sans la bonne réponse)."""

    id: str
    question: str
    options: list[str]
    subject: str
    level: str
    topic: str


class QuizAnswer(BaseModel):
    """Réponse à une question de quiz."""

    question_id: str = Field(min_length=1, max_length=36)
    answer_index: int = Field(ge=0, le=3)
    justification: str = Field(default="", max_length=500)
    # 1 = « je devine », 2 = « plutôt sûr », 3 = « sûr » (déclaré avant la correction).
    confidence: int | None = Field(default=None, ge=1, le=3)


class QuizResult(BaseModel):
    """Résultat d'une réponse de quiz."""

    question_id: str
    correct: bool
    correct_index: int
    explanation: str
    score_delta: float = 0.0
    # Erreurs consécutives sur ce thème, calculées côté serveur (intervention à 3).
    consecutive_wrong: int = 0
    # Calibration de CETTE réponse (None si la confiance n'a pas été déclarée).
    calibration: str | None = None


class CalibrationOut(BaseModel):
    """Profil de calibration de la confiance de l'élève."""

    answered: int
    overconfident_rate: float
    underconfident_rate: float
    label: str | None = None


class QuizSessionOut(BaseModel):
    """Fin de session de quiz."""

    ok: bool
    new_badges: list[BadgeOut] = Field(default_factory=list)


# ───────────────────────────── Plans d'étude ─────────────────────────────


class StudyPlanRequest(BaseModel):
    """Demande de plan d'étude."""

    exam_label: str = Field(min_length=1, max_length=200)
    target_date: datetime
    subjects: list[Subject] = Field(min_length=1, max_length=9)
    level: SchoolLevel


class StudyPlanDay(BaseModel):
    """Un jour du plan."""

    date: str
    day_label: str
    subjects: list[str]
    tasks: list[str]
    completed: bool = False


class StudyPlanOut(BaseModel):
    """Plan d'étude."""

    id: str
    title: str
    exam_label: str
    target_date: datetime
    subjects: list[str]
    level: str
    days: list[StudyPlanDay]
    is_active: bool
    created_at: datetime
    # Message d'information (ex. plan allégé car l'IA n'a pas répondu).
    notice: str | None = None


class StudyPlanDayToggle(BaseModel):
    """Coche/décoche d'un jour."""

    day_index: int = Field(ge=0, le=120)
    completed: bool


# ───────────────────────────── Examen blanc ─────────────────────────────


class ExamStartRequest(BaseModel):
    """Démarrage d'un examen blanc."""

    subject: Subject
    level: SchoolLevel
    exam_label: str = Field(default="BEPC", min_length=1, max_length=100)
    question_count: int = Field(default=10, ge=3, le=20)
    duration_min: int = Field(default=15, ge=3, le=120)
    request_id: str | None = Field(default=None, min_length=8, max_length=64)


class ExamQuestionOut(BaseModel):
    """Question d'examen."""

    attempt_id: str
    question: str
    options: list[str]
    index: int
    total: int


class ExamStartOut(BaseModel):
    """Examen démarré (le chronomètre fait foi côté serveur)."""

    exam_id: str
    duration_sec: int
    question_count: int
    expires_at: datetime
    first_question: ExamQuestionOut


class ExamAnswerRequest(BaseModel):
    """Réponse à une question d'examen (``None`` = question passée)."""

    attempt_id: str = Field(min_length=1, max_length=36)
    answer_index: int | None = Field(default=None, ge=0, le=3)


class ExamAnswerOut(BaseModel):
    """Suite de l'examen après une réponse.

    Volontairement SANS indication de réussite : en conditions d'examen la correction
    n'est dévoilée qu'à la fin (``/finish``), comme à l'examen officiel.
    """

    next_question: ExamQuestionOut | None
    finished: bool
    time_expired: bool = False


class ExamDetail(BaseModel):
    """Détail d'une question d'examen corrigée."""

    question: str
    options: list[str]
    correct_index: int
    answer_index: int | None
    is_correct: bool | None
    explanation: str | None


class ExamResultOut(BaseModel):
    """Résultat d'un examen."""

    exam_id: str
    subject: str
    level: str
    exam_label: str
    score: float
    correct_count: int
    total: int
    duration_sec: int
    details: list[ExamDetail]


# ───────────────────────────── Administration ─────────────────────────────


class SubjectCount(BaseModel):
    """Compteur par matière."""

    subject: str
    count: int


class LevelCount(BaseModel):
    """Compteur par niveau."""

    level: str
    count: int


class DayCount(BaseModel):
    """Compteur par jour."""

    date: str
    count: int


class AdminStats(BaseModel):
    """Statistiques anonymisées de la plateforme."""

    total_users: int
    active_users_7d: int
    total_sessions: int
    total_messages: int
    total_exercises: int
    total_quiz_attempts: int
    subject_popularity: list[SubjectCount]
    level_distribution: list[LevelCount]
    signups_by_day: list[DayCount]


# ───────────────────────────── Classes (enseignants) ─────────────────────────────


class ClassroomCreate(BaseModel):
    """Création d'une classe."""

    name: str = Field(min_length=2, max_length=150)
    level: SchoolLevel


class ClassroomOut(BaseModel):
    """Classe d'un enseignant."""

    id: str
    name: str
    invite_code: str
    level: str
    student_count: int
    created_at: datetime


class ClassroomJoin(BaseModel):
    """Rejoindre une classe par code."""

    invite_code: str = Field(min_length=4, max_length=8)


class ClassroomJoinOut(BaseModel):
    """Résultat d'une adhésion."""

    ok: bool
    already_member: bool
    classroom_name: str


class JoinedClassroom(BaseModel):
    """Classe rejointe par l'élève (il peut la quitter)."""

    id: str
    name: str
    level: str
    joined_at: datetime


class WeakConcept(BaseModel):
    """Concept faible (maîtrise effective)."""

    subject: str
    concept: str
    score: float


class StudentSummary(BaseModel):
    """Vue d'UN élève, visible uniquement par l'enseignant de la classe rejointe."""

    user_id: str
    full_name: str | None
    username: str
    total_sessions: int
    total_questions: int
    streak_days: int
    subject_scores: dict[str, float]
    weakest_concepts: list[WeakConcept]
    joined_at: datetime


class ClassAverage(BaseModel):
    """Moyenne de classe par matière."""

    subject: str
    average_score: float


class ClassroomReport(BaseModel):
    """Rapport d'une classe."""

    classroom_id: str
    classroom_name: str
    student_count: int
    students: list[StudentSummary]
    class_averages: list[ClassAverage]
