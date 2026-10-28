"""Configuration de l'application (variables d'environnement uniquement).

Aucune valeur secrète n'a de défaut : ``SECRET_KEY`` est obligatoire et doit
faire au moins 32 caractères (voir ``scripts/generate_secret.py``).
"""

from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Paramètres typés, lus depuis l'environnement (et ``.env`` en développement).

    Attributes:
        ENVIRONMENT: ``development``, ``test`` ou ``production``.
        SECRET_KEY: Clé de signature des JWT (>= 32 caractères, obligatoire).
        DATABASE_URL: URL SQLAlchemy ou URL Neon/Render (``postgresql://...``).
    """

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    APP_NAME: str = "EduIA Tuteur Intelligent"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    LOG_LEVEL: str = "INFO"

    # --- Sécurité -------------------------------------------------------
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Base de données ------------------------------------------------
    # Neon free : pooler activé (hôte « -pooler »), connexions peu nombreuses.
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"
    DB_POOL_SIZE: int = 3
    DB_MAX_OVERFLOW: int = 2
    DB_POOL_RECYCLE_S: int = 300
    # Neon : utiliser l'URL DIRECTE (sans « -pooler ») pour Alembic si disponible.
    MIGRATION_DATABASE_URL: str = ""

    # --- LLM ------------------------------------------------------------
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.7
    LLM_TIMEOUT_S: float = 30.0
    LLM_MAX_RETRIES: int = 2

    # --- Tuteur ---------------------------------------------------------
    RAG_TOP_K: int = 5
    MAX_CONVERSATION_HISTORY: int = 20
    DAILY_LLM_QUOTA: int = 80
    DAILY_QUIZ_SESSION_CAP: int = 20

    # --- HTTP -----------------------------------------------------------
    # Liste séparée par des virgules (ex. "https://eduia.pages.dev,http://localhost:5173").
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024

    # --- Limitation de débit (en mémoire, 1 instance : suffisant en gratuit)
    RATE_LIMIT_ENABLED: bool = True
    RL_AUTH_PER_MIN: int = 10
    RL_REGISTER_PER_HOUR: int = 10
    RL_LLM_PER_MIN: int = 20
    RL_JOIN_PER_MIN: int = 10

    RL_RESET_PER_HOUR: int = 5
    # Pédagogie : vérification des clés de QCM (1 appel LLM de plus par question) et banque.
    QUIZ_VERIFY_KEYS: bool = True
    QUESTION_BANK_ENABLED: bool = True
    QUESTION_BANK_MIN_UNSEEN: int = 5
    QUESTION_BANK_MAX_PER_KEY: int = 40
    QUESTION_BANK_SUSPECT_MIN_SERVED: int = 15
    QUESTION_BANK_SUSPECT_MAX_RATE: float = 0.15

    # --- Mot de passe oublié (e-mail) -----------------------------------
    # Sans SMTP_HOST, aucun e-mail n'est envoyé (en développement le lien est écrit dans les journaux).
    FRONTEND_URL: str = "http://localhost:5173"
    RESET_TOKEN_EXPIRE_MINUTES: int = 30
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_TIMEOUT_S: float = 15.0

    # --- Observabilité --------------------------------------------------
    SENTRY_DSN: str = ""

    @field_validator("SECRET_KEY")
    @classmethod
    def _secret_not_placeholder(cls, value: str) -> str:
        """Refuse les valeurs d'exemple évidentes."""
        lowered = value.lower()
        if lowered.startswith(("change", "changez", "your", "votre")):
            raise ValueError("SECRET_KEY ressemble à une valeur d'exemple : générez-en une vraie.")
        return value

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        """En production : pas de SQLite (disque éphémère)."""
        if self.ENVIRONMENT == "production" and self.DATABASE_URL.startswith("sqlite"):
            raise ValueError(
                "SQLite est interdit en production (disque éphémère) : utilisez PostgreSQL (Neon)."
            )
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        """Origines CORS autorisées, nettoyées."""
        return [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        """Vrai si ``ENVIRONMENT == "production"``."""
        return self.ENVIRONMENT == "production"


settings = Settings()  # type: ignore[call-arg]  # SECRET_KEY vient de l'environnement
