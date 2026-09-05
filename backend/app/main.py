import time
from math import ceil

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.health import router as health_router
from app.api.papers import router as papers_router
from app.core.rate_limit import limiter
from app.core.settings import get_settings

# P5-C4: process start for /metrics uptime. Stdlib only — no prometheus_client
# dependency on purpose (avoids new wheel + image bake); Prometheus text
# exposition is built by hand below.
START_TIME = time.monotonic()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title=settings.app_name, version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(papers_router)

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        if not request.url.path.startswith("/papers"):
            return await call_next(request)
        limit = get_settings().rate_limit_per_minute
        if limit <= 0:
            return await call_next(request)
        limiter.per_minute = limit
        key = getattr(request.client, "host", None) or "unknown"
        retry_after = limiter.check(key)
        if retry_after is not None:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded, retry shortly"},
                headers={"Retry-After": str(int(ceil(retry_after)))},
            )
        return await call_next(request)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> PlainTextResponse:
        # Minimal Prometheus text exposition (stdlib only, no new infra).
        # /health is untouched. DB failure -> omit papers_total (unknown).
        uptime = time.monotonic() - START_TIME
        lines = [
            "# HELP research_radar_uptime_seconds Process uptime in seconds.",
            "# TYPE research_radar_uptime_seconds gauge",
            f"research_radar_uptime_seconds {uptime:.3f}",
        ]
        try:
            from sqlalchemy import text

            from app.db.session import SessionLocal

            with SessionLocal() as db:
                count = db.execute(text("SELECT COUNT(*) FROM paper")).scalar()
            lines.extend(
                [
                    "# HELP research_radar_papers_total Total number of papers stored.",
                    "# TYPE research_radar_papers_total gauge",
                    f"research_radar_papers_total {int(count)}",  # type: ignore[arg-type]
                ]
            )
        except Exception:
            pass
        return PlainTextResponse(
            "\n".join(lines) + "\n",
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return app


app = create_app()