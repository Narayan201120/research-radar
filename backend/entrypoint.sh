#!/bin/sh
set -e

echo "[entrypoint] waiting for PostgreSQL..."
python - <<'PY'
import os
import sys
import time

import psycopg

url = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://research:research@postgres:5432/research_radar",
).replace("postgresql+psycopg://", "postgresql://")

for attempt in range(30):
    try:
        psycopg.connect(url, connect_timeout=2).close()
        print("[entrypoint] PostgreSQL ready")
        break
    except Exception as exc:
        if attempt == 29:
            print(f"[entrypoint] PostgreSQL unavailable: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(1)
PY

if [ -f alembic.ini ] && command -v alembic >/dev/null 2>&1; then
    echo "[entrypoint] running migrations"
    alembic upgrade head
fi

if [ "${INGEST_ON_BOOT:-true}" = "true" ] && [ -f scripts/ingest_openalex.py ]; then
    echo "[entrypoint] self-healing data (ingest if empty, similarity if missing)"
    python -m scripts.ingest_openalex --boot
fi

echo "[entrypoint] starting uvicorn"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000