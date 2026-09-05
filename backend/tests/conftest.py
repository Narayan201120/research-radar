import os

import app.models  # noqa: F401  register all tables on Base.metadata
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.api.deps import get_db
from app.core.settings import get_settings
from app.db.base import Base
from app.main import app


@pytest.fixture()
def db():
    """A fresh in-memory SQLite schema for every test (hermetic isolation).

    StaticPool + check_same_thread=False lets TestClient's ASGI thread share the
    single in-memory connection. ``paper_embedding`` is created via raw DDL
    (vector-typed on Postgres; plain TEXT here) so ingest-path embedding writes
    run unguarded on both dialects.
    """
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS paper_embedding ("
                "paper_id INTEGER PRIMARY KEY REFERENCES paper(id) ON DELETE CASCADE, "
                "embedding TEXT NOT NULL)"
            )
        )
    testing = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield engine, testing
    engine.dispose()


@pytest.fixture()
def session(db):
    engine, testing = db
    s = testing()
    yield s
    s.close()


@pytest.fixture()
def client(db):
    engine, testing = db

    def _override_get_db():
        with testing() as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clear_rate_limit():
    from app.core.rate_limit import clear_rate_limit

    clear_rate_limit()
    yield
    clear_rate_limit()


# ---------------------------------------------------------------------------
# Postgres / ParadeDB fixtures — only active when DATABASE_URL points to a
# live ParadeDB instance. Tests using these fixtures are marked
# ``@pytest.mark.postgres`` and skip gracefully when Docker is not up.
# ---------------------------------------------------------------------------

_PG_TABLES = (
    "paper_embedding",
    "paper_author",
    "paper_topic",
    "ingest_state",
    "paper",
    "author",
    "topic",
)


def _pg_url() -> str:
    # honor explicit env first, fall back to Settings default
    return os.getenv("DATABASE_URL") or get_settings().database_url


def _is_postgres_url(url: str) -> bool:
    return url.startswith("postgresql")


@pytest.fixture(scope="session")
def pg_engine():
    url = _pg_url()
    if not _is_postgres_url(url):
        pytest.skip("postgres tests require DATABASE_URL with postgresql scheme")
    engine = create_engine(url, poolclass=NullPool, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - connection failure path
        engine.dispose()
        pytest.skip(f"postgres not reachable at {url}: {exc}")
    # ensure migrations are applied (idempotent)
    try:
        from alembic import command as alembic_command
        from alembic.config import Config as AlembicConfig

        cfg = AlembicConfig("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", url)
        alembic_command.upgrade(cfg, "head")
    except Exception:
        pass
    yield engine
    engine.dispose()


@pytest.fixture()
def pg_session(pg_engine):
    with pg_engine.begin() as conn:
        for table in _PG_TABLES:
            conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
        # reset serial PKs so seeded ids are deterministic
        conn.execute(text("SELECT setval(pg_get_serial_sequence('paper','id'), 1, false)"))
        conn.execute(text("SELECT setval(pg_get_serial_sequence('author','id'), 1, false)"))
        conn.execute(text("SELECT setval(pg_get_serial_sequence('topic','id'), 1, false)"))
    SessionLocal = sessionmaker(bind=pg_engine, autoflush=False, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture()
def pg_client(pg_engine, pg_session):
    def _override_get_db():
        yield pg_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()