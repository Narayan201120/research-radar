# Research Radar — Revised Architecture (v2)

Review of `architecture.md` + `implementation-plan.md` against `ASSESSMENT.md`.
Changes are marked with **Δ** and justified. Everything else is unchanged from the assessment contract.

---

## 1. Changes from v1

| # | Area | Change | Why |
|---|------|--------|-----|
| 1 | Docker/ops | Auto-migration + auto-seed on boot (**Δ critical**) | Reviewer runs `docker compose up --build` and must see a working app with data. Nothing in v1 ensures Alembic runs or that 300–500 papers exist. |
| 2 | Connectivity | Direct browser→backend (`localhost:8000`) + CORS; pin env strategy (**Δ critical**) | Next.js bakes `NEXT_PUBLIC_*` at build time; unstated connectivity is the #1 end-to-end failure mode. |
| 3 | Ops | `/health` endpoint + compose healthchecks (**Δ**) | Frontend/backend must not race Postgres. `depends_on: healthy` + `pg_isready` costs nothing. |
| 4 | Schema | `Topic.slug` added; `abstract`/`doi` nullable; junction PKs/cascades; indexes specified | API contract uses `topic=computer-vision` (a slug) — v1 model had no slug. |
| 5 | Schema | `PaperSimilarity` stores only per-paper top-5 (≤5 rows/paper), not a pair matrix | Full matrix = 2×N×(N−1)/2 ≈ 250k rows with directionality bugs; top-5 = 2,500 rows, exactly what the endpoint returns. |
| 6 | Similarity | Recompute is a step of idempotent ingestion (truncate + rebuild in one transaction) | Otherwise re-ingest leaves stale similarity rows — violates rerunnable/idempotent. |
| 7 | Ingestion | Pin OpenAlex call details: runtime topic-ID resolution, cursor pagination, `from_publication_date`, retry/backoff, `abstract_inverted_index` reconstruction, title-less paper skip | v1 had no detail; wrong OpenAlex params = empty DB = failed eval. |
| 8 | API | `page_size` cap (1–100), deterministic sort (`publication_year DESC, id DESC`), 404 contract, items shape, ILIKE wildcard escaping | v1 contract underspecified → unstable pagination and edge-case 500s. |
| 9 | Testing | SQLite-compatible models (no Postgres-only types), pure-Python similarity core, fake OpenAlex client for idempotency test | Assessment says "tests must pass" but v1 plan has no test strategy for ingestion. |
| 10 | Frontend | Client-side fetch only (no SSR fetch to backend); hardcode the two topic slugs as constants; plain `useEffect` + state (no SWR/react-query) | SSR fetch inside a container cannot reach `localhost:8000`. Two topics → no `/topics` endpoint needed. |
| 11 | Hygiene | `.gitignore`/`.dockerignore`, one commit per phase | "Do not commit raw data dumps" + "meaningful git history" are checklist items. |

---

## 2. Data Model

Design priorities (per assessment): searchability, query simplicity, normalization, readability. Avoid premature optimization.

### paper

| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | surrogate, stable across re-ingests |
| openalex_id | VARCHAR(64) UNIQUE NOT NULL | dedup key for upsert; indexed via UNIQUE |
| title | TEXT NOT NULL | skip papers with empty title (rare, corrupt records) |
| abstract | TEXT NULL | OpenAlex often omits abstracts; must be nullable |
| publication_year | SMALLINT NOT NULL | filter target |
| doi | VARCHAR(255) NULL | display-only metadata |
| cited_by_count | INT NOT NULL DEFAULT 0 | display metadata; also ingest sort key |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |

Indexes:
- `UNIQUE(openalex_id)` — required for idempotent upsert (ON CONFLICT).
- `(publication_year)` — year filter selectivity.
- No index on title/abstract. ILIKE `%q%` cannot use a B-tree; at 300–500 rows a sequential scan is sub-millisecond. Adding `pg_trgm`/GIN is premature optimization (documented tradeoff).

Why it exists: canonical record of a paper; all reads flow from here.

Tradeoffs: no `publication_date`, `venue`, `language` — display-only, not required by any filter, adds normalization burden for zero eval points.

### author

| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| openalex_id | VARCHAR(64) UNIQUE NOT NULL | dedup key |
| name | TEXT NOT NULL | |

Indexes: none beyond UNIQUE. Author filter is `name ILIKE '%x%'`; an index is useless for that pattern at this scale (documented).

Why it exists: `GET /papers` and detail pages must show authors; normalized so author filter is a clean join.

Tradeoff: no author-position/affiliation metadata — out of scope, zero eval value.

### topic

| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| openalex_id | VARCHAR(64) UNIQUE NOT NULL | |
| name | TEXT NOT NULL | display |
| slug | VARCHAR(64) UNIQUE NOT NULL | `computer-vision`, `large-language-models` — set deterministically at ingest |

Why it exists: topic filter and detail-page topics. Slug is required because the API contract filters by slug. Only 2 rows ever.

### paper_author (junction)

- `paper_id` FK → paper.id ON DELETE CASCADE
- `author_id` FK → author.id ON DELETE CASCADE
- PK (`paper_id`, `author_id`)
- Index on `author_id` (author→papers lookup)

### paper_topic (junction)

- Same pattern; index on `topic_id`.

Junction tables are the normalized way to model M:N; composite PKs prevent dupes by construction. Cascades keep re-ingestion clean.

### paper_similarity

| Column | Type | Notes |
|--------|------|-------|
| paper_id | BIGINT FK CASCADE | the query paper |
| similar_paper_id | BIGINT FK CASCADE | a top-5 neighbor |
| similarity_score | DOUBLE PRECISION | 0..1, rounded to 4 dp in API |
| PK (`paper_id`, `similar_paper_id`) | | |

Holds **only** each paper's own top-5 (max 5 rows per `paper_id`, ~2,500 rows at 500 papers). Rebuilt wholesale on every ingestion run.

Why the table instead of computing at request time:
- Trivial endpoint (`SELECT … ORDER BY score DESC`), deterministic snapshot, inspectable via SQL.
- No file artifact (pickle matrix) to mount into the container and keep fresh.
- Recompute cost is milliseconds.

Tradeoffs: needs regeneration on re-ingest (solved — it is part of ingestion) and stores redundancy (each direction separately). Alternative (rejected): persist pickled sparse TF-IDF matrix, compute top-5 per request — removes the table but adds a storage artifact and per-request compute for zero eval benefit.

---

## 3. API Contract

Base: FastAPI, prefix `/api` optional — pick one (recommend no prefix; contract matches assessment exactly).

### GET /health

`200 {"status": "ok"}` — used by compose healthchecks and frontend error diagnostics.

### GET /papers

Query params (all optional):

| Param | Default | Validation | Semantics |
|-------|---------|-----------|-----------|
| page | 1 | ≥ 1 | offset-based (fine at ≤500 rows) |
| page_size | 20 | 1..100 (cap) | rows per page |
| q | — | trim; empty ⇒ no-op | case-insensitive substring over `title OR abstract`, ILIKE with `%`/`_` escaped |
| year | — | int | exact match on publication_year |
| topic | — | slug | `EXISTS` join via paper_topic + topic.slug |
| author | — | name | case-insensitive substring on author.name via join |

Sort (fixed, documented): `publication_year DESC, id DESC`. Deterministic order = stable pagination. Relevance sorting is explicitly out of scope (no rankable full-text search — documented tradeoff).

Response (exactly as contracted, items shape now defined):

```json
{
  "items": [{
    "id": 1, "title": "...", "publication_year": 2025,
    "cited_by_count": 42,
    "authors": [{"id": 3, "name": "A. Smith"}]
  }],
  "total": 137, "page": 1, "page_size": 20
}
```

`total` = count of the fully-filtered query (second query; fine at this scale).

### GET /papers/{id}

- `200` full detail: `id, title, abstract, publication_year, doi, cited_by_count, created_at, authors: [{id,name}], topics: [{id,name,slug}]`
- `404 {"detail": "Paper not found"}` for unknown/non-int id.

### GET /papers/{id}/similar

- `404` if paper unknown.
- `200` bare array (as contracted), always ≤ 5, self excluded by construction:

```json
[{"id": 2, "title": "...", "similarity_score": 0.84}]
```

Errors: FastAPI's 422 for validation; uniform `{"detail": ...}` 404s. No custom error envelope (simplicity).

---

## 4. Find Similar Papers

Pipeline (all at ingestion time):

1. Pull `title` and (reconstructed) `abstract` from DB. Missing abstract ⇒ title only. Both empty ⇒ paper is still searchable but contributes zero text; zero-norm guard (skip as neighbor, never crash).
2. `TfidfVectorizer(lowercase=True, stop_words="english", min_df=1, ngram_range=(1,2))` over the corpus.
3. Cosine similarity, excluding self.
4. Keep top-5 per paper; `TRUNCATE paper_similarity` + bulk insert in one transaction.
5. Round scores to 4 decimals at the API layer only.

Why: deterministic, no external API, trivially explainable in README — exactly the assessment's stated reason. sklearn is a single pip dependency and keeps the core a pure function (`corpus → pairs`) so it is unit-testable without a DB.

Edge cases to test: empty corpus, single paper, papers with empty abstract, duplicate titles, all-zero vectors.

---

## 5. Ingestion (OpenAlex)

CLI entry: `python -m scripts.ingest` (runnable via `docker compose exec backend …` or auto on boot).

Per topic (two: Computer Vision, Large Language Models):

1. Topic IDs are **hardcoded** (resolved once from OpenAlex and fixed) with env overrides `OPENALEX_TOPIC_CV_ID` / `OPENALEX_TOPIC_LLM_ID`. Rationale: fewer moving parts, deterministic, no runtime dependency on OpenAlex's topics taxonomy. README documents: "Topic IDs were resolved from OpenAlex and fixed to guarantee reproducible ingestion." Map name → fixed slug.
2. Fetch: `GET /works?filter=topics.id:{id},from_publication_date:2023-01-01&sort=cited_by_count:desc&per-page=100&cursor=*&mailto=…`. Cursor-paginate until ~200–250 papers per topic (target 400–500 total). Lower the date bound automatically if a topic yields <200 (keeps "recent" while meeting the count).
3. `sleep 0.2` between requests; retry on 429/5xx (3 attempts, backoff). Rate limits are the most common live-ingestion failure.
4. Reconstruct `abstract` from `abstract_inverted_index` (sort by position, join). Skip records with no title (corrupt); keep no-abstract records.
5. Normalize: paper, authors, topics, relations.

Upsert order (idempotency):
- `INSERT … ON CONFLICT (openalex_id) DO UPDATE` for papers (refreshes `cited_by_count`), authors, topics (fix slug/name).
- Rebuild relations: delete + re-insert junction rows for the fetched papers (or `ON CONFLICT DO NOTHING`).
- Regenerate `paper_similarity` (step 4 above).

Running twice yields identical row counts — this is a test, not an assumption.

Data is never committed to git; `.gitignore` blocks `*.jsonl`, `*.csv`, dumps.

---

## 6. Docker Topology & Readiness

```text
frontend (next dev/standalone, :3000)
    │  browser calls http://localhost:8000 directly (client-side fetch only)
    ▼
backend  (uvicorn :8000)
    │  DATABASE_URL=postgresql+psycopg://…@postgres:5432/research_radar
    ▼
postgres (postgres:16-alpine, named volume `pgdata`)
```

- **postgres**: healthcheck `pg_isready -U ${POSTGRES_USER}`.
- **backend**: `depends_on: postgres: condition: service_healthy`. Entrypoint:
  1. wait for pg (short `pg_isready` poll loop — belt and braces),
  2. `alembic upgrade head`,
  3. if `INGEST_ON_BOOT=true` (default) **and** `SELECT count(*) FROM paper` = 0 → run ingestion,
  4. `uvicorn app.main:app`.
- **frontend**: `depends_on: backend: service_healthy`. Build arg `NEXT_PUBLIC_API_BASE_URL` with default `http://localhost:8000`.

Connectivity (the part that fails most often):
- Browser fetches `http://localhost:8000` (backend publishes `8000:8000`), so `NEXT_PUBLIC_*` baked at build time stays correct in docker *and* local dev.
- The base URL is configurable: the frontend reads `process.env.NEXT_PUBLIC_API_BASE_URL` everywhere. Docker Compose passes it as a build arg (default `http://localhost:8000`); a later deployment just changes the env value — no code changes. Add `NEXT_PUBLIC_API_BASE_URL` to `.env.example`.
- FastAPI `CORSMiddleware` allows origins from env (`CORS_ORIGINS`, default `http://localhost:3000,http://127.0.0.1:3000`).
- All frontend data fetching is client-side (no SSR fetch — a server component inside the frontend container cannot resolve `localhost:8000`).

All env vars have defaults inside `docker-compose.yml` → `docker compose up --build` works with zero manual setup, per the Docker requirement.

---

## 7. Frontend

- `/` (search page, client component): debounced (300ms) `q` input, filters (year input, author input, topic select from two hardcoded slugs in `lib/constants.ts`), pagination controls (page + total from API), skeleton loading, empty state ("no papers match"), error state with retry button. No router/state library.
- `/papers/[id]` (detail page): full metadata, authors, topics, similar-papers list with scores; same three states. "Back to search" link.
- `lib/api.ts`: typed fetch wrapper with `AbortController` (cancels stale debounced requests).
- `types/`: PaperSummary, PaperDetail, SimilarPaper.
- No frontend test suite (assessment explicitly deprioritizes it); keep components dumb.

---

## 8. Testing

pytest + FastAPI TestClient. Backend unit tests run against SQLite in-memory → models must avoid Postgres-only types (they do: only TEXT/INT/BOOL/TIMESTAMPTZ-ish). This keeps `pytest` runnable without docker.

Priority (per assessment):
1. **API filtering**: q, year, topic, author — individually and combined.
2. **Search**: case-insensitivity, wildcard escaping (`%`, `_`), empty q.
3. **Pagination**: page boundaries, page_size cap (422), stable order, total.
4. **Similar logic**: pure-function tests on a synthetic corpus (top-5, self-exclusion, empty-abstract, zero-norm).
5. **Ingestion idempotency**: run ingest twice with a fake OpenAlex client (`httpx.MockTransport` — no network in tests), assert identical counts.

Commands (README): `docker compose run --rm backend pytest`.

---

## 9. Folder Structure

Per assessment, plus explicit placements:

```text
backend/
├── alembic/                     # single initial migration (schema + indexes)
├── app/
│   ├── api/                     # papers.py, health.py
│   ├── core/settings.py         # pydantic-settings, env-driven
│   ├── db/                      # engine, session, Base
│   ├── models/                  # paper.py, author.py, topic.py, similarity.py
│   ├── schemas/                 # Pydantic response/query models
│   ├── services/
│   │   ├── similarity.py        # pure TF-IDF pipeline (unit-testable)
│   │   └── openalex.py          # client: cursor pagination, retry, abstract reconstruction
│   └── main.py                  # app factory, CORS, routers
├── scripts/ingest_openalex.py   # CLI + idempotent orchestrator
├── tests/                       # api/, services/
├── entrypoint.sh                # wait → migrate → seed-if-empty → uvicorn
├── Dockerfile
└── requirements.txt
```

---

## 10. Revised Implementation Plan (mapped to git history)

One commit per completed deliverable, conventional messages.

| Phase | Deliverable | Verifiable |
|-------|------------|------------|
| 1 | Compose skeleton: postgres + backend boot, `/health`, healthchecks | `docker compose up --build` → healthy |
| 2 | Models + single Alembic migration (schema, indexes, cascades) | migrate idempotent; SQLite models import clean |
| 3 | OpenAlex client + ingestion CLI with fake-client test; `.gitignore` | ingest → 400–500 rows; rerun → identical counts |
| 4 | Similarity service + `paper_similarity` rebuild in ingestion | unit tests green; SQL shows ≤5/paper |
| 5 | `/papers`, `/papers/{id}`, `/papers/{id}/similar` + CORS | curl checks, API tests green |
| 6 | Backend test suite (filtering/search/pagination/similar/idempotency) | `pytest` green |
| 7 | Search page: debounce, filters, pagination, three states | manual E2E in browser |
| 8 | Detail page + similar UI + retry/error handling | manual E2E |
| 9 | README (all 7 required sections), final review + score table, final commit | checklist passes |

Ordering rationale: ingestion before API means API tests exercise real-shaped data; similarity is inside ingestion so the AI feature is never out of sync.

---

## 11. Risks (ranked by probability of failing evaluation) & Mitigations

| # | Risk | P | Mitigation |
|---|------|---|-----------|
| 1 | `docker compose up` yields an empty DB (no auto-migrate/seed) | High | Entrypoint: migrate + ingest-if-empty (Δ1) |
| 2 | Frontend can't reach backend (env bake-time trap, no CORS) | High | Client-side fetch to `localhost:8000` + CORS middleware + fixed build arg (Δ2) |
| 3 | OpenAlex ingest fails live (wrong filters, rate limit, taxonomy drift) | High | Runtime topic resolution + env overrides, cursor pagination, retry/backoff, date fallback (Δ7) |
| 4 | Similarity stale after re-ingest or crashes on empty text | Med | Rebuild inside ingestion transaction; zero-norm guard (Δ6) |
| 5 | Abstract reconstruction bug → sparse search results | Med | Inverted-index reconstruction unit-tested; nullable abstract |
| 6 | Tests can't run without docker/network | Med | SQLite-compatible models, fake OpenAlex client |
| 7 | Pagination instability / validation 500s | Med | Fixed sort, page_size cap, 404/422 contract |
| 8 | Missing loading/empty/error states | Med | All three views implement all three states (Δ10) |
| 9 | Dump files or node_modules committed | Low | `.gitignore` + `.dockerignore`, no data files in repo |
| 10 | Postgres/backend race at boot | Low | `depends_on: service_healthy` + `pg_isready` poll |

---

## 12. Intentional Simplifications (document in README)

- ILIKE substring search instead of full-text (pg_trgm/FTS) — 500 rows doesn't justify it; relevance ranking out of scope.
- Offset pagination instead of keyset — data set is tiny and stable.
- Materialized top-5 similarity instead of live TF-IDF — deterministic, inspectable, no file artifacts.
- Two topics hardcoded as frontend constants instead of a `/topics` endpoint — the topic set is fixed by the assessment.
- No auth, no caching layer, no background workers — explicitly out of scope.
- Plain `useEffect` fetch instead of SWR/react-query — one page, three views.
