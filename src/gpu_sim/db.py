"""Path and session management for the SQLite application database."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from gpu_sim.models import Base


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "artifacts" / "gpuflow.db"
_DEFAULT_DATABASE: "Database | None" = None


def configured_database_path() -> Path:
    configured = os.environ.get("GPUFLOW_DB_PATH")
    return Path(configured).resolve() if configured else DEFAULT_DB_PATH.resolve()


class Database:
    def __init__(self, path: Path | str = DEFAULT_DB_PATH) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{self.path.as_posix()}",
            future=True,
            connect_args={"check_same_thread": False},
        )
        event.listen(self.engine, "connect", _configure_sqlite)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine, expire_on_commit=False, autoflush=False, future=True
        )

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def dispose(self) -> None:
        self.engine.dispose()


def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def get_database() -> Database:
    global _DEFAULT_DATABASE
    if _DEFAULT_DATABASE is None:
        _DEFAULT_DATABASE = Database(configured_database_path())
    return _DEFAULT_DATABASE


def reset_default_database_connection() -> None:
    """Dispose the process-wide DB connection before changing its path."""
    global _DEFAULT_DATABASE
    if _DEFAULT_DATABASE is not None:
        _DEFAULT_DATABASE.dispose()
    _DEFAULT_DATABASE = None
