import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.api.health import router as health_router
from app.api.papers import router as papers_router
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