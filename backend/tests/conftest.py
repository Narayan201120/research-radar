import app.models  # noqa: F401  register all tables on Base.metadata
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
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