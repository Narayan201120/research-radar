from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db

router = APIRouter(tags=["health"])

HealthSession = Annotated[Session, Depends(get_db)]


@router.get("/health")
def health(db: HealthSession) -> JSONResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "unreachable"},
        )
    return JSONResponse(content={"status": "ok", "database": "ok"})
