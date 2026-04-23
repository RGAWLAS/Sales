"""Pytest fixtures — spin up a file-based SQLite DB per session so models have
access to a live engine without touching the default app DB."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolated_db(tmp_path_factory) -> None:
    """Point the app at a throwaway SQLite file before any imports touch it."""
    tmp_dir = tmp_path_factory.mktemp("db")
    db_path = tmp_dir / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ.setdefault("LOG_LEVEL", "WARNING")
    # Logs dir must exist; route it into the temp dir as well.
    os.environ["TENDER_LOGS_DIR"] = str(tmp_dir)


@pytest.fixture()
def db_session():
    from app.database import Base, SessionLocal, engine, init_db

    init_db()
    # Reset to a clean slate between tests.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
