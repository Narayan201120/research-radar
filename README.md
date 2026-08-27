# Research Radar

Search and explore recent research papers in computer vision and large language
models. Backed by a PostgreSQL database seeded from [OpenAlex](https://openalex.org),
with **BM25 ranked search** and **Find Similar Papers** powered by semantic embeddings.

## Stack

| Layer      | Technology |
| ---------- | ---------- |
| Frontend   | Next.js 14 (App Router), React 18, Tailwind CSS |
| Backend    | FastAPI, SQLAlchemy 2.0, Alembic |
| Database   | PostgreSQL 16 via `paradedb/paradedb:0.25.3-pg16` (pgvector + pg_search BM25, single image) |
| Search     | ParadeDB BM25 (`paper_search_idx` on `title`+`abstract`, `paradedb.score` ranking) with ILIKE fallback; `?ranked=true` opts into relevance ordering |
| Similarity | Dual-path: semantic `paper_embedding` (384-d `all-MiniLM-L6-v2` via fastembed ONNX, HNSW `vector_cosine_ops`, ANN at read time) with legacy TF-IDF `paper_similarity` snapshot fallback — contract unchanged, vectors win when present |
| Tests      | pytest (85 tests, SQLite in-memory hermetic + Postgres-marked integration gate in CI) |
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
4. builds the TF-IDF similarity snapshot, and
5. starts uvicorn.

A guarded runner decides between *full ingest*, *similarity-only rebuild*, and *skip*
on every boot, so restarts are safe and idempotent.

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
- Normalized schema: `paper`, `author`, `topic`, `paper_author`, `paper_topic`,
  `paper_similarity`, `paper_embedding`, `ingest_state`.
- Live corpus: `ingest_state` watermarks (`last_full_ingest_at`/`last_incremental_at`
  per topic) drive `from_updated_date` delta fetches (`updated_date:desc`) capped at
  200/topic; `backfill_watermarks` upgrades pre-existing static volumes.

### Search

- **Ranked mode** (`GET /papers?ranked=true&q=...`): BM25 via `paper_search_idx`
  (`USING paradedb (id, title, abstract) WITH (key_field='id')`, `paradedb.score`
  ordering, `score DESC, publication_year DESC, id DESC`). Year/topic/author filters
  AND-combine with the BM25 match. Requires `q` (422 otherwise). ILIKE remains the
  default (`ranked=false`); on non-PostgreSQL dialects (tests) `ranked=true` degrades
  to the legacy result set — same contract, relevance ordering is the feature.
- **Legacy mode** (default): boolean ILIKE AND-matching over `title`/`abstract`
  (deprecated for search, retained as fallback until removal).

### Similarity (Find Similar Papers)

- **Semantic path (current):** `paper_embedding(paper_id PK/FK, embedding vector(384))`
  with HNSW `vector_cosine_ops`; `GET /papers/{id}/similar` probes for a vector first
  → ANN `ORDER BY embedding <=> self` (filtered `>0`, rounded to 4dp, deterministic
  tie-break by id). Write cost is `O(Δ)` — only new or title/abstract-changed papers
  are (re-)embedded during ingest; citation bumps do not trigger re-embedding.
- **Legacy snapshot:** `paper_similarity` top-5 cosine rows regenerated on every
  ingest when `SIMILARITY_BACKEND=tfidf` (the current default). `tfidf` vectorization:
  lowercase, English stopwords, 1–2 grams over `title + abstract`; `>0` scores only,
  self excluded. Snapshot rebuild is skipped in `embeddings` mode.
- Papers with no text (no title/abstract, as returned by OpenAlex for ~12% of
  works) contribute zero vectors and have no similarity rows (permanently skipped by
  `scripts/backfill_embeddings.py`). At 500 papers all live rows are embedded.

## API

### `GET /papers`

Query parameters (all optional except `q` when `ranked=true`):

| Param      | Default | Semantics |
| ---------- | ------- | --------- |
| `q`        | —       | Search terms. `ranked=false` (default): case-insensitive ILIKE substring, all whitespace-separated terms must match. `ranked=true`: BM25 relevance query over `title`+`abstract` (`paradedb.match`, same `q` string) — requires `q` (422 otherwise) |
| `ranked`   | `false` | `false` → legacy ILIKE path byte-identical. `true` → BM25 relevance ordering (`paradedb.score DESC, publication_year DESC, id DESC`), same response shape (ordering is the feature, no score exposed) |
| `year`     | —       | Exact `publication_year` |
| `topic`    | —       | Topic slug (`computer-vision` / `large-language-models`) |
| `author`   | —       | Case-insensitive substring on author name |
| `page`     | 1       | ≥ 1 |
| `page_size`| 20      | 1..100 |

Filters combine with AND in both modes. Sort: legacy `publication_year DESC, id DESC`; ranked `paradedb.score DESC, publication_year DESC, id DESC` (deterministic pagination). Ranked results are relevance-ordered; the `q` string is passed directly to ParadeDB query parsing (Tantivy).

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
docker compose exec backend python -m pytest        # hermetic SQLite suite
python -m pytest -q                                 # same, from backend/ with local venv
```

85 tests, hermetic per-test in-memory SQLite schema (no network): similarity edge
cases (empty corpus, single paper, zero vectors, duplicate titles, determinism),
API endpoints (search/filters/pagination/404s/LIKE escaping, `?ranked` validation
and dialect-guard degradation), `similar` dialect guard (SQLite falls back to
snapshot even with a stored vector), ingest idempotency (fake client fetched
twice → 0 new rows), the real OpenAlex client (httpx `MockTransport`), abstract
reconstruction, and the DOI verifier. Postgres-marked integration suite
(`@pytest.mark.postgres`, ParadeDB service container in CI) is the gate for
BM25 relevance and ANN similarity assertions.

## Repository layout

```
backend/
  app/api/          # FastAPI routes (papers, health)
  app/models/       # SQLAlchemy models
  app/schemas/      # Pydantic response models
  app/services/     # ingest, openalex client, similarity, embeddings (EmbeddingProvider + vector helpers)
  alembic/          # migrations (ingest_state, vector/bm25 extensions, paper_embedding + hnsw, paper_search_idx)
  scripts/          # ingest_openalex (--similarity-only, --boot, --incremental/--since), scheduler, backfill_embeddings
  tests/            # pytest suite (conftest SQLite shim for paper_embedding)
  requirements.in/txt  # pip-tools pinned (40 packages)
frontend/
  app/              # Next.js pages (search, /papers/[id], 404)
  components/       # SearchExplorer, PaperCard, Pagination
  lib/              # typed API client, config, debounce hook
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
| `SIMILARITY_BACKEND`    | `tfidf` (`tfidf` \| `embeddings` — controls ingest embedding writes + snapshot rebuild skip; `/similar` is data-driven regardless) |
| `EMBEDDING_MODEL_NAME`  | `sentence-transformers/all-MiniLM-L6-v2` (384-d, baked into image at `/app/.fastembed`) |
| `API_BASE_URL` (frontend) | `http://backend:8000` |
| `NEXT_PUBLIC_API_BASE_URL` (frontend build arg) | `http://localhost:8000` |