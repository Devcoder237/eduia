"""Alembic : la migration initiale s'applique, correspond aux modèles, et se défait."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db.database import Base
from app.models import models  # noqa: F401

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic(db_file: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{db_file}"}
    return subprocess.run(  # noqa: S603 - commande fixe, arguments contrôlés par le test
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.fixture
def migrated_db(tmp_path: Path) -> Path:
    db_file = tmp_path / "migrated.db"
    result = _alembic(db_file, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    return db_file


def test_upgrade_creates_every_model_table(migrated_db: Path) -> None:
    engine = create_engine(f"sqlite:///{migrated_db}")
    tables = set(inspect(engine).get_table_names())
    assert set(Base.metadata.tables) <= tables
    assert "alembic_version" in tables
    engine.dispose()


def test_migration_matches_models(migrated_db: Path) -> None:
    """Aucune table, colonne ou index ne manque ni ne dépasse entre modèles et migration."""
    engine = create_engine(f"sqlite:///{migrated_db}")
    with engine.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    structural = [
        d
        for d in diffs
        if isinstance(d, tuple)
        and d[0]
        in {
            "add_table",
            "remove_table",
            "add_column",
            "remove_column",
            "add_index",
            "remove_index",
            "add_constraint",
            "remove_constraint",
        }
    ]
    assert structural == []


def test_upgrade_is_idempotent_and_downgrade_works(migrated_db: Path) -> None:
    assert _alembic(migrated_db, "upgrade", "head").returncode == 0
    down = _alembic(migrated_db, "downgrade", "base")
    assert down.returncode == 0, down.stderr
    engine = create_engine(f"sqlite:///{migrated_db}")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()
