# Research Radar

Search and explore recent research papers in computer vision and large language
models. Backed by a PostgreSQL database seeded from [OpenAlex](https://openalex.org),
with **BM25 ranked search**, **RRF hybrid**, **Find Similar Papers** powered by semantic embeddings, and **local bookmarks/history**.

## Stack

| Layer      | Technology |
| ---------- | ---------- |
| Frontend   | Next.js 16 (App Router, Turbopack), React 19, Tailwind CSS |
| Backend    | FastAPI, SQLAlchemy 2.0, Alembic |
| Database   | PostgreSQL 16 via `paradedb/paradedb:0.25.3-pg16` (pgvector + pg_search BM25, single image) |
| Search     | ParadeDB BM25 (`paper_search_idx` on `title`+`abstract`, `paradedb.score` ranking) with ILIKE fallback; `?ranked=true` BM25, `?hybrid=true` RRF `K=60` (vector 10 + BM25 10 → 10, filters after, `422` if both) |
| Similarity | Semantic `paper_embedding` (384-d `all-MiniLM-L6-v2` via fastembed ONNX, HNSW `vector_cosine_ops`, ANN at read time, `O(Δ)` write + `O(log N)` read) — `paper_similarity` snapshot removed in `a1b2c3d4e5f6` |
| Tests      | pytest (86 tests: 79 SQLite hermetic + 7 Postgres integration — `pytest -m postgres` for BM25/ANN/hybrid) |
| Infra      | Docker Compose (postgres + backend + frontend + scheduler sidecar) |

## Quick start

```bash
docker compose up -d --build
```

- Frontend: http://localhost:3000
- API: http://localhost:8000 — interactive docs at http://localhost:8000/docs
- Health: http://localhost:8000/health

On first boot the backend automatically:
1. waits for PostgreSQL,
2. runs Alembic migrations,
3. ingests 500 papers (two OpenAlex topics, 2023+) if the database is empty,
4. embeds title+abstract for every paper (`paper_embedding` HNSW), and
5. starts uvicorn.

A guarded boot runner (`--boot`) decides between *full ingest* when empty else *skip*,
so restarts are safe and idempotent; no nightly `O(N²)` rebuild.

A separate **scheduler sidecar** keeps the corpus current: it fetches only
papers changed since each topic's watermark (`ingest_state` table) immediately
at startup — catching up any churn while the stack was down — and then every
`INGEST_INTERVAL_HOURS` (default 24). New papers are added, existing ones are
refreshed in place, nothing duplicates, and a failed cycle is retried on the
next tick without taking anything down.

## Data & ingestion

- Two topics: **Computer Vision** (`openalex_topic_cv_id`) and **Large Language
  Models** (`openalex_topic_llm_id`), configurable via environment variables.
- Papers fall within 300–500 (a date window is widened only when OpenAlex cannot
  fill an earlier range; the database keeps whatever the widest successful window
  delivered).
- Ingestion is **idempotent**: re-running upserts papers by `openalex_id`, never
  duplicates author/topic relations, and writes are crash-consistent (data +
  watermark + embeddings share the same transaction).
- Normalized schema: `paper` (`abstract_source`/`abstract_recovered_at` provenance in `b2c3d4e5f6a7`), `author`, `topic`, `paper_author`, `paper_topic`,
  `paper_embedding` (`vector(384)` HNSW), `ingest_state` (`paper_similarity` dropped in `a1b2c3d4e5f6`). Abstract recovery: `paper.abstract IS NULL` → Crossref JATS → arXiv Atom → publisher HTML (`citation_abstract` meta or Springer `#Abs1`/`Elsevier author` sections, `springer`/`elsevier`/`html_generic` provenance, `beautifulsoup4`/`lxml`) waterfall (57 recoverable post re-seed, `1/57` recovered live via `arxiv` — `http://arxiv.org/abs/2408.16932` for dead `10.1007/9` — `56` remain targeting HTML, re-embedded, daily hook `LIMIT 20`).
- Live corpus: `ingest_state` watermarks (`last_full_ingest_at`/`last_incremental_at`
  per topic) drive `from_updated_date` delta fetches (`updated_date:desc`) capped at
  200/topic; `backfill_watermarks` upgrades pre-existing static volumes.

### Search

- **Hybrid mode** (`GET /papers?hybrid=true&q=...`): RRF `K=60` fusion of vector `top 10` (HNSW `embedding <=> query`) + BM25 `top 10` (`paradedb.score`), fused to `10` (port of `rag_web_app` `retriever.py:135`), filters `year/topic/author` applied **after** fusion (Option A), `page` paginates fused list. Requires `q` (`422` otherwise), `hybrid` and `ranked` mutually exclusive (`422`). `hybrid total` is fused size (≤20), not full match count — `ranked`/`ILIKE` totals are full counts. Live `q=attention` → `hybrid 14` vs `ranked 68` vs `ILIKE 69` (top-K vs full).
- **Ranked mode** (`GET /papers?ranked=true&q=...`): BM25 via `paper_search_idx`
  (`USING paradedb (id, title, abstract) WITH (key_field='id')`, `paradedb.score`
  ordering, `score DESC, publication_year DESC, id DESC`). Year/topic/author filters
  AND-combine with the BM25 match. Requires `q` (422 otherwise). ILIKE remains the
  default (`ranked=false`); on non-PostgreSQL dialects (tests) `ranked=true` degrades
  to the legacy result set — same contract, relevance ordering is the feature.
- **Legacy mode** (default): boolean ILIKE AND-matching over `title`/`abstract`
  (deprecated for search, retained as fallback until removal).

### Similarity (Find Similar Papers)

- `paper_embedding(paper_id PK/FK, embedding vector(384))` with HNSW
  `vector_cosine_ops`; `GET /papers/{id}/similar` returns ANN neighbors
  `ORDER BY embedding <=> self` (filtered `>0`, rounded to 4dp, deterministic
  tie-break by id, `[]` if no vector). Write cost is `O(Δ)` — only new or
  title/abstract-changed papers are (re-)embedded during ingest; citation bumps
  do not trigger re-embedding. No `paper_similarity` snapshot — TF-IDF
  `scikit-learn` path removed in `a1b2c3d4e5f6` (image shrinks ~100MB compressed).
- Papers with no text (no title/abstract, as returned by OpenAlex for ~12% of
  works) contribute zero vectors and return `[]` (permanently skipped by
  `scripts/backfill_embeddings.py`). At 500 papers all live rows are embedded.

## API

### `GET /papers`

Query parameters (all optional except `q` when `ranked/hybrid=true`):

| Param      | Default | Semantics |
| ---------- | ------- | --------- |
| `q`        | —       | Search terms. `ranked=false, hybrid=false` (default): case-insensitive ILIKE substring, all whitespace-separated terms must match. `ranked=true`: BM25 relevance query over `title`+`abstract` (`paradedb.match`, same `q` string) — requires `q` (422 otherwise). `hybrid=true`: RRF `K=60` of vector 10 + BM25 10 → 10, requires `q` (422), `hybrid` and `ranked` mutually exclusive (422) |
| `ranked`   | `false` | `false` → legacy ILIKE path byte-identical. `true` → BM25 relevance ordering (`paradedb.score DESC, publication_year DESC, id DESC`), same response shape (ordering is the feature, no score exposed) |
| `hybrid`   | `false` | `false` → not hybrid. `true` → RRF hybrid (see Search above), `422` if `ranked` also `true` |
| `year`     | —       | Exact `publication_year` |
| `topic`    | —       | Topic slug (`computer-vision` / `large-language-models`) |
| `author`   | —       | Case-insensitive substring on author name |
| `ids`      | —       | Comma id list (max 100, invalid ignored, empty → empty). AND-combined (Option A intersect-then-rank for Saved) |
| `page`     | 1       | ≥ 1 |
| `page_size`| 20      | 1..100 |

Filters combine with AND in both modes. Sort: legacy `publication_year DESC, id DESC`; ranked `paradedb.score DESC, publication_year DESC, id DESC` (deterministic pagination). Ranked results are relevance-ordered; the `q` string is passed directly to ParadeDB query parsing (Tantivy). `ids` enables full-corpus Saved search (`?ids=1,2,3&saved` client flow).

```json
{
  "items": [{
    "id": 253,
    "title": "Attention Is All You Need",
    "publication_year": 2017,
    "cited_by_count": 6659,
    "authors": [{"id": 1252, "name": "Ashish Vaswani"}]
  }],
  "total": 70,
  "page": 1,
  "page_size": 20
}
```

### `GET /papers/{id}`

Full detail: `id, title, abstract, publication_year, doi, cited_by_count,
created_at, authors[{id,name}], topics[{id,name,slug}]`.
`404 {"detail": "Paper not found"}` for unknown or non-integer ids.

### `GET /papers/{id}/similar`

Top-5 similar papers, self-excluded by construction, scores rounded to 4 decimals:

```json
[{"id": 2, "title": "LLaMA: ...", "similarity_score": 0.8765}]
```

## Tests

```bash
docker compose exec backend python -m pytest        # all tests (86: 79 hermetic + 7 gate live — hybrid adds 2, HTML adds 5)
python -m pytest -q                                 # hermetic from backend/ with local venv (79, 7 skipped without Docker)
python -m pytest -m postgres -q                     # Postgres gate only (7 tests, requires ParadeDB — BM25/ANN/hybrid)
```

86 tests: 79 hermetic per-test in-memory SQLite schema (no network) + 7
Postgres/ParadeDB integration — API endpoints (search/filters/pagination/404s/LIKE
escaping, `?ranked`/`?hybrid` validation `422` and dialect-guard degradation, `hybrid` RRF `K=60` filters-after), `similar` returns
`[]` on SQLite (no vector/HNSW), ingest idempotency (fake client fetched twice →
0 new rows), the real OpenAlex client (httpx `MockTransport`), abstract
reconstruction (including `abstract_recovery` Crossref→arXiv→HTML waterfall, `publisher_extract` meta/section), DOI
verifier (private-IP block), and live BM25 relevance + ANN similarity + hybrid fusion (`tests/test_postgres.py`,
`HashingFakeProvider`/`FastEmbedProvider`, TRUNCATE per test). Hermetic stays green without Docker
(7 skipped); CI `services: postgres` (`paradedb/paradedb:0.25.3-pg16`) runs both
steps for 86 passed.

Abstract backfill: `docker compose exec backend python -m scripts.backfill_abstracts --dry-run` (57 recoverable, `1/57` via `arxiv`, remainder via HTML) → `python -m scripts.backfill_abstracts` (polite 0.5s, re-embeds).

## Repository layout

```
backend/
  app/api/          # FastAPI routes (papers, health)
  app/models/       # SQLAlchemy models (paper now has abstract_source/recovered_at)
  app/schemas/      # Pydantic response models
  app/services/     # ingest, openalex client, embeddings, abstract_recovery (Crossref→arXiv→HTML waterfall), publisher_extract
  alembic/          # migrations (ingest_state, vector/bm25 extensions, paper_embedding + hnsw, paper_search_idx, drop paper_similarity, abstract provenance)
  scripts/          # ingest_openalex (--boot, --incremental/--since), scheduler, backfill_embeddings, backfill_abstracts
  tests/            # pytest suite (conftest SQLite shim, @pytest.mark.postgres gate, abstract_recovery)
  requirements.in/txt  # pip-tools pinned
frontend/
  app/              # Next.js pages (search, /papers/[id], 404)
  components/       # SearchExplorer, PaperCard, Pagination, BookmarkButton, HistoryPusher
  lib/              # typed API client, config, debounce hook, bookmarks (localStorage)
  public/           # logo assets
```

## Environment variables

| Variable                | Default |
| ----------------------- | ------- |
| `POSTGRES_USER/PASS/DB` | `research` / `research` / `research_radar` |
| `DATABASE_URL`          | `postgresql+psycopg://research:research@postgres:5432/research_radar` |
| `CORS_ORIGINS`          | `http://localhost:3000,http://127.0.0.1:3000` |
| `OPENALEX_MAILTO`       | `research-radar@example.com` |
| `OPENALEX_TOPIC_CV_ID`  | `T10531` |
| `OPENALEX_TOPIC_LLM_ID` | `T10181` |
| `INGEST_ON_BOOT`        | `true` |
| `INGEST_INTERVAL_HOURS` | `24` |
| `SCHEDULER_RETRY_MINUTES` | `5` (short retry after failed incremental ingest; else waits `INGEST_INTERVAL_HOURS`) |
| `SIMILARITY_BACKEND`    | `embeddings` (`embeddings` default; `tfidf` via env no longer has code — revert via `git revert`) |
| `EMBEDDING_MODEL_NAME`  | `sentence-transformers/all-MiniLM-L6-v2` (384-d, baked into image at `/app/.fastembed`) |
| `API_BASE_URL` (frontend) | `http://backend:8000` |
| `NEXT_PUBLIC_API_BASE_URL` (frontend build arg) | `http://localhost:8000` |