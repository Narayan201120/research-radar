# Research Radar

Search and explore recent research papers in computer vision and large language
models. Backed by a PostgreSQL database seeded from [OpenAlex](https://openalex.org),
with a **Find Similar Papers** feature powered by TF-IDF vector similarity.

## Stack

| Layer      | Technology                                        |
| ---------- | ------------------------------------------------- |
| Frontend   | Next.js 14 (App Router), React 18, Tailwind CSS   |
| Backend    | FastAPI, SQLAlchemy 2.0, Alembic                  |
| Database   | PostgreSQL 16                                     |
| Similarity | scikit-learn `TfidfVectorizer` + cosine similarity |
| Tests      | pytest (45 tests, SQLite in-memory, no network)   |
| Infra      | Docker Compose                                    |

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

## Data & ingestion

- Two topics: **Computer Vision** (`openalex_topic_cv_id`) and **Large Language
  Models** (`openalex_topic_llm_id`), configurable via environment variables.
- Papers fall within 300–500 (a date window is widened only when OpenAlex cannot
  fill an earlier range; the database keeps whatever the widest successful window
  delivered).
- Ingestion is **idempotent**: re-running upserts papers by `openalex_id`, never
  duplicates author/topic relations, and rebuilds similarity inside the same
  transaction.
- Normalized schema: `paper`, `author`, `topic`, `paper_author`, `paper_topic`,
  `paper_similarity`.

### Similarity (Find Similar Papers)

- Persisted snapshot: every paper stores its **top-5 most similar** papers with a
  cosine score, regenerated on every ingest (`TRUNCATE` + rebuild in one
  transaction).
- Vectorization: lowercase, English stopwords, 1–2 grams over `title + abstract`.
- Score `> 0` rows only (no zero-score "noise" neighbors); paper vs. itself is
  always excluded; ties are broken deterministically.
- Papers with no text (no title/abstract, as returned by OpenAlex for ~12% of
  works) contribute zero vectors and have no similarity rows.

## API

### `GET /papers`

Query parameters (all optional):

| Param      | Default | Semantics                                             |
| ---------- | ------- | ----------------------------------------------------- |
| `q`        | —       | Case-insensitive substring over title/abstract; all whitespace-separated terms must match |
| `year`     | —       | Exact `publication_year`                              |
| `topic`    | —       | Topic slug (`computer-vision` / `large-language-models`) |
| `author`   | —       | Case-insensitive substring on author name             |
| `page`     | 1       | ≥ 1                                                   |
| `page_size`| 20      | 1..100                                                |

Filters combine with AND. Sort is fixed: `publication_year DESC, id DESC`
(deterministic pagination; relevance ranking deliberately out of scope —
ILIKE substring search over title/abstract, documented tradeoff).

```json
{
  "items": [{
    "id": 431,
    "title": "Attention Is All You Need",
    "publication_year": 2025,
    "cited_by_count": 6600,
    "authors": [{"id": 3, "name": "Ada Lovelace"}]
  }],
  "total": 137,
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
docker compose exec backend python -m pytest
```

45 tests, run against a per-test in-memory SQLite schema (hermetic, no network):
similarity edge cases (empty corpus, single paper, zero vectors, duplicate
titles, determinism), API endpoints (search/filters/pagination/404s/LIKE
escaping), ingest idempotency (fake client fetched twice → 0 new rows), the
real OpenAlex client (httpx `MockTransport`, no network), and abstract
reconstruction.

## Repository layout

```
backend/
  app/api/          # FastAPI routes
  app/models/       # SQLAlchemy models
  app/schemas/      # Pydantic response models
  app/services/     # ingest, OpenAlex client, similarity
  alembic/          # migrations
  scripts/          # ingest_openalex (--similarity-only, --boot)
  tests/            # pytest suite
frontend/
  app/              # Next.js pages (search, /papers/[id], 404)
  components/       # SearchExplorer, PaperCard, Pagination
  lib/              # typed API client, config, debounce hook
  public/           # logo assets
```

## Environment variables

| Variable                | Default                                |
| ----------------------- | -------------------------------------- |
| `POSTGRES_USER/PASS/DB` | `research` / `research` / `research_radar` |
| `DATABASE_URL`          | `postgresql+psycopg://research:research@postgres:5432/research_radar` |
| `CORS_ORIGINS`          | `http://localhost:3000,http://127.0.0.1:3000` |
| `OPENALEX_MAILTO`       | `research-radar@example.com`           |
| `OPENALEX_TOPIC_CV_ID`  | `T10531`                               |
| `OPENALEX_TOPIC_LLM_ID` | `T10181`                               |
| `INGEST_ON_BOOT`        | `true`                                 |
| `API_BASE_URL` (frontend) | `http://backend:8000`                |