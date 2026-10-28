"""Fixtures communes : base SQLite en mémoire, client HTTP, faux LLM (aucun appel réseau)."""

import os
import re
from collections.abc import AsyncIterator, Callable
from typing import Any

# Doit précéder tout import de ``app`` : la configuration est lue à l'import.
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-0123456789abcdef"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["OPENAI_API_KEY"] = "sk-test-not-a-real-key"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["SENTRY_DSN"] = ""

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import update  # noqa: E402

from app.core import llm  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.db import database as dbmod  # noqa: E402
from app.main import app  # noqa: E402
from app.models.models import User  # noqa: E402
from app.services import quiz_service  # noqa: E402
from app.services.badge_service import ensure_badges  # noqa: E402

PASSWORD = "Secret123"


class FakeLLM:
    """Remplace ``app.core.llm`` : réponses déterministes et compteurs d'appels."""

    def __init__(self) -> None:
        self.json_calls = 0
        self.stream_calls = 0
        self.fail = False
        self.rubric_rate = 1.0
        self.numeric_answer: Any = "4"
        self.stream_chunks = ["Bonjour ", "élève !"]
        self.stream_error_after: int | None = None
        self.last_system_prompt = ""
        self.json_prompts: list[str] = []
        # Réponse du « vérificateur » de clé de QCM (1 = la bonne réponse du faux LLM).
        self.verifier_answer: int = 1

    async def complete_json(
        self, messages: list[llm.Message], *, max_tokens: int = 900, temperature: float = 0.5
    ) -> dict[str, Any]:
        self.json_calls += 1
        if self.fail:
            raise llm.LLMError(status_code=502, detail="Le tuteur IA a rencontré un problème.")
        prompt = messages[-1]["content"]
        self.json_prompts.append(prompt)
        if "rubric_scores" in prompt:
            labels = re.findall(r"^- (.+?) \(bareme", prompt, re.M)
            return {
                "rubric_scores": [
                    {"critere": label, "taux": self.rubric_rate, "justification": "ok"} for label in labels
                ],
                "feedback": "Bravo !",
                "errors": [],
                "concepts_to_review": [],
                "positive_points": ["Bonne démarche"],
                "next_step": "Continue",
            }
        if '"days"' in prompt:
            count = int(re.search(r"exactement (\d+) jours", prompt).group(1))  # type: ignore[union-attr]
            return {
                "days": [
                    {
                        "day_label": f"Jour {i + 1}",
                        "subjects": ["mathematiques"],
                        "tasks": ["Réviser", "Exercices"],
                    }
                    for i in range(count)
                ]
            }
        if '"answer_index"' in prompt:
            return {"answer_index": self.verifier_answer}
        if '"correct_index"' in prompt:
            n = self.json_calls
            return {
                "question": f"Combien font 2 + {n} ?",
                "options": [f"{n + 1}", f"{n + 2}", f"{n + 3}", f"{n + 4}"],
                "correct_index": 1,
                "explanation": "Parce que l'addition est commutative.",
            }
        if '"statement"' in prompt:
            return {
                "statement": f"Calcule 2 + 2 (variante {self.json_calls}).",
                "solution": "2 + 2 = 4",
                "hints": ["Additionne"],
                "concepts": ["addition"],
                "estimated_min": 5,
                "numeric_answer": self.numeric_answer,
                "grading_rubric": [
                    {"critere": "Méthode", "points": 0.5},
                    {"critere": "Résultat", "points": 0.5},
                ],
            }
        return {"score": 0.9, "feedback": "ok", "errors": [], "concepts_to_review": [], "positive_points": []}

    async def complete_text(self, messages: list[llm.Message], **_: Any) -> str:
        self.last_system_prompt = messages[0]["content"]
        return "Réponse du tuteur."

    async def stream_text(self, messages: list[llm.Message]) -> AsyncIterator[str]:
        self.stream_calls += 1
        self.last_system_prompt = messages[0]["content"]
        for index, chunk in enumerate(self.stream_chunks):
            if self.stream_error_after is not None and index >= self.stream_error_after:
                raise llm.LLMError(status_code=502, detail="Flux interrompu.")
            yield chunk


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    fake = FakeLLM()
    monkeypatch.setattr(llm, "complete_json", fake.complete_json)
    monkeypatch.setattr(llm, "complete_text", fake.complete_text)
    monkeypatch.setattr(llm, "stream_text", fake.stream_text)
    # Ordre des options déterministe : la bonne réponse du faux LLM est l'index 1.
    monkeypatch.setattr(quiz_service, "shuffle_options", lambda q: q)
    # Les tests existants comptent les appels LLM : vérification de clé et banque sont
    # désactivées par défaut ; tests/test_pedagogy.py les active explicitement.
    monkeypatch.setattr(settings, "QUIZ_VERIFY_KEYS", False)
    monkeypatch.setattr(settings, "QUESTION_BANK_ENABLED", False)
    return fake


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Client HTTP sur l'application, avec une base SQLite vierge par test."""
    engine = dbmod.init_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(dbmod.Base.metadata.create_all)
    async with dbmod.AsyncSessionLocal() as session:
        await ensure_badges(session)
    limiter.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    await engine.dispose()


class Account:
    """Compte de test connecté."""

    def __init__(self, email: str, tokens: dict[str, Any]) -> None:
        self.email = email
        self.tokens = tokens

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens['access_token']}"}


@pytest.fixture
def signup(client: AsyncClient) -> Callable[..., Any]:
    async def _signup(name: str = "alice") -> Account:
        email = f"{name}@example.com"
        reg = await client.post(
            "/api/auth/register",
            json={"email": email, "username": name, "password": PASSWORD, "full_name": name.title()},
        )
        assert reg.status_code == 201, reg.text
        login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
        assert login.status_code == 200, login.text
        return Account(email, login.json())

    return _signup


async def set_flags(email: str, **flags: bool) -> None:
    """Attribue des rôles (is_teacher / is_admin) directement en base."""
    async with dbmod.AsyncSessionLocal() as session:
        await session.execute(update(User).where(User.email == email).values(**flags))
        await session.commit()


@pytest.fixture
def limits_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Active le limiteur de débit pour les tests qui le vérifient."""
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
