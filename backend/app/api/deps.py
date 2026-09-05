from collections.abc import Generator

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def require_api_key(request: Request) -> None:
    from app.core.settings import get_settings

    key = get_settings().api_key.strip()
    if not key:
        return None
    import secrets

    provided = request.headers.get("x-api-key", "")
    if secrets.compare_digest(provided, key):
        return None
    raise HTTPException(status_code=401, detail="Invalid or missing API key")