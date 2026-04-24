"""SQLAlchemy engine and session factory."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


def _ensure_sqlite_dir(url: str) -> None:
    prefix = "sqlite:///"
    if url.startswith(prefix):
        rel = url[len(prefix):]
        path = Path(rel)
        if not path.is_absolute():
            path = settings.base_dir / path
        path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.database_url)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a DB session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create tables if they do not yet exist, then apply light migrations."""
    # Import models so metadata is registered.
    from app import models  # noqa: F401

    Base.metadata.create_all(engine)
    _apply_lightweight_migrations()


def _apply_lightweight_migrations() -> None:
    """Idempotent schema fixes for pre-existing SQLite databases.

    We don't use Alembic — SQLite + a small app doesn't justify it — so this
    covers the one-off column adds we've introduced after the initial ship.
    """
    insp = inspect(engine)
    if "tenders" not in insp.get_table_names():
        return

    cols = {c["name"] for c in insp.get_columns("tenders")}
    statements: list[str] = []
    if "category" not in cols:
        statements.append(
            "ALTER TABLE tenders ADD COLUMN category VARCHAR(20) "
            "NOT NULL DEFAULT 'TENDER'"
        )

    if not statements:
        return

    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
