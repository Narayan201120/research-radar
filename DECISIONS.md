# DECISIONS.md — Research Radar Decision Log

Running log of every design, architectural, and informational decision made while
evolving Research Radar from a static assessment corpus into a live, searchable,
semantically-aware system. Entries are numbered oldest-first. Superseded decisions
are marked and linked to their successor.

Maintenance rule: update this file *before* executing a major change, or immediately
after an informational query establishes a direction. One sequential ID per entry.

---

## [DEC-001] Adopt Phased Evolution Roadmap (Foundations → Live Corpus → Search → Semantics)
- **Date/Context:** 2026-08-22, immediately post-interview planning session.
- **Context/What:** Restructure the project's future as four phases instead of ad-hoc changes: Phase 0 (pins/CI/hardening), Phase 1 (watermark-based live ingestion + scheduler sidecar), Phase 2/merged-3 (ParadeDB BM25 search + MiniLM/pgvector semantic similarity).
- **The "Why":** Unpinned deps and no CI made every later change unverifiable; incremental ingestion without foundations would be flying blind. Sequencing was chosen so each phase's verification gates de-risk the next.
- **Improvement over Previous Solution:** Replaced "one big rewrite" ambition with independently shippable, individually verifiable milestones.
- **Pros:**
  - Each phase lands green-testable in isolation
  - Rollback boundaries are clean (one compose line, one commit)
- **Cons & Trade-offs:**
  - Slower time-to-feature than a big-bang approach
  - Transitional dual-paths (e.g., TF-IDF alongside embeddings) add temporary complexity
- **Status:** Implemented (Phases 0–1 complete; Phase 3 in progress at Commit 6 of 8 — BM25 ranked search landed; embeddings/similarity live)

## [DEC-002] Pin All Backend Dependencies via pip-tools
- **Date/Context:** 2026-08-22, Phase 0.
- **Context/What:** Added `backend/requirements.in` (top-level deps) compiled by `pip-tools` into fully-pinned `requirements.txt` — 40 packages incl. transitives (numpy 2.5.2, scipy 1.18.1, fastapi 0.141.1).
- **The "Why":** Audit finding C2 — only sqlalchemy was bounded; builds were non-reproducible and supply-chain upgrades unreviewed. pip-tools chosen over poetry/uv for zero workflow disruption (Dockerfile keeps consuming `requirements.txt`).
- **Improvement over Previous Solution:** Floating `fastapi`, unpinned scikit-learn etc. → exact reproducible set with annotated provenance (`# via -r requirements.in`).
- **Pros:**
  - Reproducible Docker builds and CI
  - Upgrade = deliberate diff review
- **Cons & Trade-offs:**
  - Lockfile churn on any dep change
  - No wheel hashes (deliberate: hash-pinning breaks behind some proxies)
- **Status:** Implemented

## [DEC-003] Add GitHub Actions CI (pytest + tsc + next build)
- **Date/Context:** 2026-08-22, Phase 0.
- **Context/What:** `.github/workflows/ci.yml` with two jobs: backend (Python 3.12, pinned install, pytest) and frontend (Node 20 matching Dockerfile, `npm ci` → `tsc --noEmit` → `next build`). Later extended with a `services:` ParadeDB container for upcoming Postgres-marked integration tests.
- **The "Why":** Audit C3 — the 54-test suite only ran manually inside containers.
- **Improvement over Previous Solution:** Verification moved from "remember to run it" to automatic on push/PR.
- **Pros:**
  - Hermetic suite needs no service containers; fast feedback
  - Service container pre-provisioned for Phase 3 integration tests
- **Cons & Trade-offs:**
  - CI minutes consumed per push
- **Status:** Implemented

## [DEC-004] `/health` Probes the Database Through the DI Session
- **Date/Context:** 2026-08-22, Phase 0.
- **Context/What:** Health endpoint executes `SELECT 1` via the same `get_db` dependency routers use; returns 200 `{"status":"ok","database":"ok"}` or 503 `{"status":"unhealthy","database":"unreachable"}`.
- **The "Why":** Audit W4 — static `/health` gated frontend startup while unable to detect DB loss. DI-session routing (vs global engine) keeps TestClient overrides hermetic.
- **Improvement over Previous Solution:** Compose healthcheck now reflects actual serving capability; degraded states surface as container-unhealthy.
- **Pros:**
  - Meaningful orchestration signal
  - Two new tests cover both paths
- **Cons & Trade-offs:**
  - Healthcheck adds one trivial query per interval
- **Status:** Implemented

## [DEC-005] Run Containers as Non-Root Users
- **Date/Context:** 2026-08-22, Phase 0.
- **Context/What:** Both Dockerfiles gained `USER` (backend: dedicated `appuser`; frontend: stock `node`) with ownership fixes post-build.
- **The "Why":** Audit W3 — root-running containers are unnecessary container-escape surface.
- **Improvement over Previous Solution:** Runtime processes drop from UID 0 to unprivileged users; verified via `whoami` inside built images.
- **Pros:**
  - Standard hardening baseline; zero behavioral change for this workload
- **Cons & Trade-offs:**
  - Host-mounted volumes must be world-readable (alembic versions mount)
- **Status:** Implemented

## [DEC-006] Credential Hygiene: Settings-Derived DSN Everywhere
- **Date/Context:** 2026-08-22, Phase 0.
- **Context/What:** Removed hardcoded `research:research@postgres...` DSN from `scripts/check_dois.py`; it now derives from `get_settings()` with a sys.path bootstrap. Default creds remain in settings/compose as dev defaults (documented pattern).
- **The "Why":** Audit C1 — credentials bypassing the Settings layer were invisible to env rotation.
- **Improvement over Previous Solution:** Single source of truth for DB location; ops scripts honor `DATABASE_URL`.
- **Pros:**
  - Env rotation reaches all consumers
- **Cons & Trade-offs:**
  - Default dev credentials still exist by design (reviewer experience); prod deployment must override
- **Status:** Implemented

## [DEC-007] Defer Next.js 14 → 16 Migration; Fix What's Fixable Now
- **Date/Context:** 2026-08-22, Phase 0 → superseded 2026-08-23.
- **Context/What:** `npm audit` surfaced 21 high advisories rooted in Next 14.2.x EOL-for-security. Applied non-breaking `audit fix` (nanoid); explicitly deferred the breaking Next 16 upgrade (React 19, async params APIs). **Superseded by DEC-026** — migrated to `next@16.3.3`/`react@19.2.8` (`frontend/package.json:10`), `params`/`searchParams` → `Promise` (`frontend/app/papers/[id]/page.tsx:7`, `frontend/app/page.tsx:11`), `tsc --noEmit` + `next build` (Turbopack) green, `npm audit` → `0 vulnerabilities`.
- **The "Why":** Most listed CVEs require unused features (middleware, rewrites, server actions, next/image); RSC-class issues remain but migration mid-Phase-0 would destabilize foundations.
- **Improvement over Previous Solution:** Silent vulnerability exposure → tracked, scoped migration item with honest exposure analysis.
- **Pros:**
  - Foundations land without framework churn
- **Cons & Trade-offs:**
  - Known RSC cache-poisoning class exposure persists until migration
  - App Router RSC usage means partial applicability — cannot dismiss entirely
- **Status:** Superseded by DEC-026 (Implemented)

## [DEC-008] Docker Hygiene Conventions (cleanup on demand, stop-don't-delete)
- **Date/Context:** 2026-08-22, between phases.
- **Context/What:** Deleted 4 stale/unneeded images keeping only `postgres:16-alpine` at the time (~3.2GB reclaimed); later sessions stop containers with `docker compose stop` preserving images/volumes/containers.
- **The "Why":** User-requested space management without losing state.
- **Improvement over Previous Solution:** Ambiguous local state → explicit policy: verification images are disposable; data volume never touched by cleanup.
- **Pros:**
  - Predictable disk usage; zero data-loss risk during pauses
- **Cons & Trade-offs:**
  - Next boot after image deletion requires `--build`
- **Status:** Implemented (ongoing convention)

## [DEC-009] Commit & Push Conventions
- **Date/Context:** 2026-08-22, first push request.
- **Context/What:** Plain descriptive lowercase sentences ("pin dependencies, add ci workflow…"), no conventional-commit prefixes; one commit per coherent milestone; interview-prep docs (`Interview_QnA.*`, `WALKTHROUGH_SCRIPT.md`) stay untracked; local `.ai/*` deletions remain unstaged pending owner decision.
- **The "Why":** Matches existing repo history style; keeps personal prep material out of public history.
- **Improvement over Previous Solution:** Ad-hoc messaging risk → consistent, reviewer-friendly history.
- **Pros:**
  - History reads as narrative; sensitive docs excluded
- **Cons & Trade-offs:**
  - Working tree permanently carries untracked files until decided
- **Status:** Implemented (ongoing convention)

## [DEC-010] Watermark-Based Incremental Ingestion Architecture
- **Date/Context:** 2026-08-22, Phase 1 (Commits: e4a9f2c81b7d migration, client refactor, ingest refactor, CLI flags).
- **Context/What:** `ingest_state` table (per-topic `last_full_ingest_at`/`last_incremental_at`); `OpenAlexClient.fetch_updated_works()` filtering `from_updated_date`, sorting `updated_date:desc`; `run_incremental_ingest()` (cap 200/topic, min-guard off); watermarks advance to fetch-*start* inside the same transaction; full ingest seeds watermarks; `backfill_watermarks()` upgrades pre-existing static databases; CLI gains `--incremental`/`--since`.
- **The "Why":** Static corpus required volume-wipe + 5–8min cold re-ingest for freshness. Key correctness fix discovered en route: delta fetch must sort by `updated_date` — `cited_by_count:desc` would permanently hide new (zero-citation) papers.
- **Improvement over Previous Solution:** Day-one cost then seconds-scale deltas replacing repeated full downloads; crash-safe (data+watermark roll back together); upgrade path for existing volumes.
- **Pros:**
  - Idempotency inherited from openalex_id upserts; missed days auto-catch-up
  - Latent bug found+fixed: cross-topic duplicate works lost second-topic membership
- **Cons & Trade-offs:**
  - Day-granularity filter can refetch same-day churn (harmless, idempotent)
  - Citation-count drift on untouched papers until OpenAlex re-indexes them
- **Status:** Implemented

## [DEC-011] Scheduler as Compose Sidecar, Not In-Process Timer
- **Date/Context:** 2026-08-22, Phase 1 (scheduler.py, compose service, INGEST_INTERVAL_HOURS=24).
- **Context/What:** Fourth compose service runs the same backend image with `python -m scripts.scheduler`: run-at-startup loop (catch-up semantics), sleep interval between cycles, failures absorbed+logged (retry next tick), SIGTERM/SIGINT graceful stop.
- **The "Why":** In-process timers die on redeploy and couple crashes; sidecar isolates failure domains and reuses the tested CLI path with zero new dependencies.
- **Improvement over Previous Solution:** Freshness moved out of boot entirely — boot guard keeps single responsibility (cold start); backend restarts never kill schedules.
- **Pros:**
  - Restart-safe; failure isolation; observable via `docker compose logs scheduler`
- **Cons & Trade-offs:**
  - Failed cycle means staleness up to full interval (short-retry backoff offered as optional enhancement, not yet requested)
  - Live-fire test absorbed a real OpenAlex 429 exactly as designed
- **Status:** Implemented

## [DEC-012] Semantic Stack: ParadeDB Image Bundling BM25 + pgvector
- **Date/Context:** 2026-08-22, Phase 3 planning (user proposal + principal-engineer refinement).
- **Context/What:** Replace planned vanilla Postgres FTS (`ts_rank`) with `paradedb/paradedb:<ver>-pg16` bundling true Tantivy-based BM25 *and* pgvector in one image swap. Pinned `0.25.3-pg16` after discovering floating `latest` ships PG18 (cannot open PG16 volume).
- **The "Why":** `ts_rank` lacks IDF (common terms under-weighted); `rank_bm25`-in-Python rejected (query-dependent scores can't be snapshotted → corpus in RAM). One image delivers both Phase 3 features.
- **Improvement over Previous Solution:** Supersedes the Phase-2 "vanilla tsvector + ts_rank" roadmap item (see DEC-013 link) — true BM25 semantics, single-image simplicity.
- **Pros:**
  - Real IDF-bearing ranking; vector capability included; SQL-native
- **Cons & Trade-offs:**
  - Debian-based image heavier than alpine; third-party dependency pinning discipline required
  - Operational surprise found: `pg_search` demands `shared_preload_libraries=pg_search` — solved declaratively via compose `command` flag so fresh clones and migrated volumes behave identically
- **Status:** Implemented (Commit 1: `c7d3f8a92e14`)

## [DEC-013] Search Ranking Strategy: BM25 Beside ILIKE, Not Replacing TF-IDF Internals
- **Date/Context:** 2026-08-22, user decision after stack discussion.
- **Context/What:** BM25 targets the `GET /papers?q=` ranked-search layer (superseding ILIKE eventually via `?ranked=true`); TF-IDF's similarity-engine role is replaced separately by embeddings (DEC-014). Ship both paths, deprecate ILIKE later.
- **The "Why":** Clarified a conflation: BM25 is query-dependent ranking (can't power a similarity snapshot), while MiniLM handles document-similarity. Three lexical engines would be redundant.
- **Improvement over Previous Solution:** Replaces boolean ILIKE AND-matching (no relevance, double-scan per request — audit W8) with proper probabilistic ranking.
- **Pros:**
  - Endpoint contracts stable during transition; instant rollback path
- **Cons & Trade-offs:**
  - Temporary dual-path maintenance until deprecation
- **Status:** Implemented (Commit 6: `f3a9c2d74b18` + `?ranked=true`)

## [DEC-014] Embeddings: all-MiniLM-L6-v2 via fastembed ONNX, ChromaDB Skipped
- **Date/Context:** 2026-08-22, user model choice + implementation refinement.
- **Context/What:** Production provider wraps `fastembed.TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")` (384-dim, apache-2.0); `EmbeddingProvider` protocol + deterministic `HashingFakeProvider` keep the suite hermetic; `sentence-transformers`/torch and adding ChromaDB-the-product both rejected (image weight; redundant vector store atop existing Postgres).
- **The "Why":** User selected the ChromaDB-default model; engineering analysis kept the weights, dropped the product — pgvector already provides storage+ANN.
- **Improvement over Previous Solution:** Lockfile confirmed zero torch (onnxruntime/tokenizers/huggingface-hub only) — lean runtime with canonical embedding quality.
- **Pros:**
  - CPU-fast inference; protocol seam makes Commit 4–5 logic testable offline
- **Cons & Trade-offs:**
  - Model-version pinning discipline needed for score comparability
- **Status:** Implemented (Commit 2: `4ca7a9e`)

## [DEC-015] Bake Model Weights Into the Image (Pull-at-Boot Rejected)
- **Date/Context:** 2026-08-22, user decision after tradeoff explanation.
- **Context/What:** Dockerfile bakes ONNX weights at build: `FASTEMBED_CACHE_PATH=/app/.fastembed`, download layer placed after `pip install` and before `COPY . .` so code edits never invalidate it; verified via cached rebuild + `--network none` smoke producing real vectors.
- **The "Why":** Pull-at-boot reintroduces the audit-W5 availability coupling we eliminated in Phase 1 (third upstream outage = stack won't start) plus version drift; baking pins the exact file by construction.
- **Improvement over Previous Solution:** Runtime network requirement: three sources (pip, npm, HF) → effectively zero at boot.
- **Pros:**
  - Hermetic clones; deterministic scores across rebuilds
- **Cons & Trade-offs:**
  - Honest correction logged: image grew 683MB → 1.19GB (+~500MB uncompressed layers vs +90MB compressed estimate)
- **Status:** Implemented (Commit 2)

## [DEC-016] Similarity Storage: `paper_embedding` + HNSW; Snapshot Table Scheduled for Removal
- **Date/Context:** 2026-08-22, Phase 3 Commit 3 (`d9e4b1c73f28`, `9c7873d`).
- **Context/What:** Raw-SQL migration creates `paper_embedding(paper_id PK/FK CASCADE, embedding vector(384))` with `hnsw (embedding vector_cosine_ops)`; no ORM model (keeps SQLite `create_all` hermetic; raw-SQL access pattern). `scripts/backfill_embeddings.py` batch-embeds missing papers, permanently skipping empty-text ones, idempotent via `ON CONFLICT DO NOTHING`. TF-IDF snapshot removal explicitly gated on Commit 7's green integration tests (user decision #3).
- **The "Why":** Query-time ANN replaces nightly O(N²) rebuilds; HNSW gives O(log N) reads at linear storage. Backfill against live data embedded **500/500** (corrected earlier ~447 estimate — abstract-less papers still have titles).
- **Improvement over Previous Solution:** Ingest cost decouples from corpus size (O(Δ) once Commit 4 lands); semantic sanity proven live — Attention Is All You Need neighbors transformer/LLM papers at 0.57–0.64 cosine vs 0.05–0.09 TF-IDF lexical overlap.
- **Pros:**
  - Append-only writes; no rebuild window where new papers lack similarity data
  - Fully tested logic even pre-Postgres (SQLite-tolerant DDL in tests)
- **Cons & Trade-offs:**
  - Approximate recall (~99%+) vs exact snapshot
  - Dual-path period: snapshot still rebuilt nightly until Commit 8 cleanup
- **Status:** Implemented (Commit 3); snapshot retirement Pending (Commit 8)

## [DEC-017] Storage Growth Analysis (User Inquiry → Direction Confirmation)
- **Date/Context:** 2026-08-22, informational query after first push.
- **Context/What:** Recorded analysis: upsert-by-openalex_id updates in place (never duplicates); snapshot is fixed-size 5×N fully replaced; watermarks are 2 rows forever; MVCC dead tuples autovacuumed → growth bounded at <75MB/year worst case; the true ceiling is compute (O(N²) rebuild ≈ dead at ~10k papers), not storage.
- **The "Why":** User concern that daily ingestion compounds storage indefinitely.
- **Improvement over Previous Solution:** Vague worry → quantified bounds; confirmed Phase 1 design contains accumulation and validated Phase 3 as the compute answer.
- **Pros:**
  - Documented expectation-setting for capacity planning
- **Cons & Trade-offs:**
  - Analysis assumed topic-filtered intake rate (~10–100 papers/day)
- **Status:** Informational (validated by subsequent design choices)

## [DEC-018] Complexity Migration: Write-Time O(N²) → Read-Time O(log N)
- **Date/Context:** 2026-08-22, informational deep-dive following "HNSW?" query.
- **Context/What:** Canonical comparison recorded: old pipeline recomputed dense N×N cosine matrix + Python top-k per ingest regardless of delta size (O(N²) time, O(N²) memory — ~800MB matrix at N=10k); new pipeline costs O(Δ) embed+insert at write and O(log N) graph traversal per read. Cost deliberately relocated from write-time to read-time because daily writes scale with corpus forever, while reads are parallelizable milliseconds.
- **The "Why":** Established the architectural justification for HNSW despite n=500 making it premature-by-design today (built ahead of scale, zero cost at current size).
- **Improvement over Previous Solution:** Turns the ~10k-paper compute wall into a non-event; eliminates snapshot-staleness class entirely.
- **Pros:**
  - Scales ingest independently of corpus; enables truly incremental Commit 4
- **Cons & Trade-offs:**
  - Per-request embedding forward pass added (~ms); approximate recall accepted (DEC-016)
- **Status:** Informational (Commit 4 wiring pending to realize full benefit)

## [DEC-019] Ingest-Embedding Integration: Provider DI, Text-Touch Semantics, SQLite DDL Shim
- **Date/Context:** 2026-08-22, Phase 3 Commit 4 (pre-implementation design entry).
- **Context/What:** Both ingest paths gain an optional `embedding_provider` parameter (pure DI — service never reads settings). Callers (`scripts/ingest_openalex.py`, `scripts/scheduler.py`) resolve the mode: `similarity_backend == "embeddings"` → real `FastEmbedProvider`, else `None`. Non-null provider ⇒ embeddings mode ⇒ **TF-IDF snapshot rebuild is skipped**; `None` ⇒ exact legacy behavior. `_apply_normalized_works` returns touched paper ids where *is_new OR title OR abstract changed* — citation-count/DOI/year bumps deliberately do NOT trigger re-embedding (they're the most common daily churn). Vector write helpers (`paper_text`, `vector_literal`, `upsert_embeddings`, `embed_papers_by_ids`) move into `services/embeddings.py`; the backfill script refactors to import them (layering: service owns logic, script owns CLI). Test fixture conftest gains a SQLite-compatible `CREATE TABLE paper_embedding (... embedding TEXT ...)` shim so all ingest tests exercise the embedding path unguarded on both dialects.
- **The "Why":** Keeps the service pure and test-injectable; avoids dialect branches in production code; prevents wasteful re-embedding of unchanged texts during daily citation drift.
- **Improvement over Previous Solution:** Realizes DEC-018's O(Δ) ingest promise — nightly O(N²) rebuild disappears once backend flips; until flip (default tfidf) zero behavior change.
- **Pros:**
  - Single knob (`provider or None`) controls both vector writes and rebuild skip
  - Embedding rows land in the same transaction as papers (crash-consistent)
- **Cons & Trade-offs:**
  - Conflation of "mode" with "provider presence" is implicit; documented here as contract
  - Snapshot goes stale if someone runs full ingest in embeddings mode mid-transition (accepted until Commit 8)
- **Status:** Implemented (Commit 4)

## [DEC-020] Similar Endpoint Reads HNSW When a Vector Exists; Legacy Snapshot Otherwise
- **Date/Context:** 2026-08-22, Phase 3 Commit 5.
- **Context/What:** `GET /papers/{id}/similar` now probes `paper_embedding` for the paper's own vector first. Present → ANN query (`ORDER BY embedding <=> self`, deterministic tie-break by id, positive-similarity filter, round to 4dp) via HNSW index. Absent → byte-identical legacy snapshot path. Dialect guard (`postgresql` only) wraps the vector branch because `<=>` has no SQLite translation — SQLite tests document the fallback explicitly.
- **The "Why":** Data-driven cutover needs no runtime flag: vectors win wherever they exist, mixed states during transition behave sensibly, rollback is trivial. Contract unchanged — same JSON shape, same `(0,1]` score range semantics.
- **The "Why" (live proof):** Paper 253 "Attention Is All You Need" served lexical scores 0.054–0.086 before deploy; immediately after, semantic neighbors at 0.567–0.635 (*End-to-End Transformer NLP* 0.635, *GQA* 0.5999, *Mistral 7B* 0.5846) with zero config change.
- **Improvement over Previous Solution:** Precomputed-snapshot reads → logarithmic graph traversal reflecting current corpus state; no staleness window between ingest and similarity availability.
- **Pros:**
  - Instant semantic quality on live stack without flipping SIMILARITY_BACKEND
  - Legacy path preserved verbatim for rollback until Commit 8 deletion
- **Cons & Trade-offs:**
  - Dialect guard is prod-code branching (accepted: `<=>` untranslatable to SQLite; integration coverage arrives in Commit 7)
  - Positive-score filter after LIMIT can shorten lists when nearest neighbors are anti-correlated (mirrors legacy ">0 only" contract)
- **Status:** Implemented (Commit 5)

## [DEC-022] BM25 Ranked Search Behind `?ranked=true`; Contract Unchanged
- **Date/Context:** 2026-08-22, Phase 3 Commit 6 (pre-implementation design entry).
- **Context/What:** `GET /papers` gains optional `ranked` flag. False/default → existing ILIKE path byte-identical. True → `q` required (422 without); raw-SQL query `p.id @@@ paradedb.match('title', :q) OR …('abstract', :q)` plus year/topic/author filters AND-combined, `ORDER BY paradedb.score(p.id) DESC, publication_year DESC, id DESC` for deterministic pagination. Ids+scores fetched via `text()` then hydrated through ORM to reuse `PaperListItem` serialization — **response contract identical, ordering is the feature, no score exposed**.
- **The "Why" (verified pre-gate):** pg_search 0.25.x renamed the access method to `USING paradedb` (`bm25` deprecated alias), mandates key_field-first + UNIQUE (our `paper.id`), allows one ParadeDB index per table, exposes `paradedb.match/score`. Live-container probe confirmed `paradedb.*` namespace (not the newer `pdb.*`) and that match syntax fails only on missing index.
- **Improvement over Previous Solution:** Supersedes boolean ILIKE AND-matching (no relevance ranking, double full-scan per request — audit W8) with true IDF-bearing BM25 relevance.
- **Pros:**
  - Zero-risk rollout behind explicit param; ILIKE remains fallback on non-PG dialects (documented degradation)
- **Cons & Trade-offs:**
  - Real ranking assertions necessarily deferred to Commit 7's Postgres-marked suite (SQLite lacks pg_search)
  - One-index-per-table means future vector-in-index consolidation would replace this definition
- **Status:** Implemented (Commit 6: `6547a92`)

## [DEC-023] Postgres Integration Gate for BM25 and ANN Similarity
- **Date/Context:** 2026-08-22, Phase 3 Commit 7.
- **Context/What:** Add `@pytest.mark.postgres` suite (`backend/tests/test_postgres.py`, 5 tests) gated on a live `paradedb/paradedb:0.25.3-pg16` instance. `pytest.ini` registers the marker; `tests/conftest.py` adds session-scoped `pg_engine` (connectivity probe + `alembic upgrade head`), per-test `pg_session` (TRUNCATE + serial reset), and `pg_client` (TestClient with real Postgres session). Hermetic SQLite suite stays 85 tests and remains the default local run; Postgres tests skip gracefully when Docker is not up (`pytest.skip`), run inside the `postgres` service on CI and via `docker compose exec backend` locally.
- **The "Why":** SQLite cannot execute `paradedb.match`/`paradedb.score` (`@@@`) or `embedding <=> vector` (HNSW). Without a real-engine gate, Commit 8's deletion of the TF-IDF snapshot and `paper_similarity` table would be unverifiable. The gate proves: BM25 orders by `score DESC` not year, filters AND-combine under ranked mode, pagination is deterministic, and `/similar` serves ANN neighbors when vectors exist (HashingFakeProvider, identical-text → top rank) and falls back to snapshot otherwise.
- **Improvement over Previous Solution:** Supersedes "trust the dialect guard" with 5 live assertions; CI now runs two steps — `pytest -q` (hermetic) and `pytest -m postgres -q` (integration) against the existing `services: postgres` ParadeDB container.
- **Pros:**
  - Zero production code touched; rollback is deleting one file
  - `HashingFakeProvider` keeps integration tests offline/deterministic (no fastembed download)
  - Windows host without Docker stays green (5 skipped), CI/container gets 90 passed (85+5)
- **Cons & Trade-offs:**
  - Per-test TRUNCATE adds ~0.5s; total suite 13–15s remains acceptable
  - Host `localhost:5432` scram auth can fail on some Windows Docker Desktop configs — live verification documented as `docker compose exec backend` (mirrors CI's `localhost` on Linux)
- **Status:** Implemented (Commit 7: `86e2678` — gate green `90 passed` container, `85 passed` host)

## [DEC-024] Cut Over to Embeddings Default and Remove TF-IDF Snapshot
- **Date/Context:** 2026-08-23, Phase 3 Commit 8 (final).
- **Context/What:** Flip `similarity_backend` default `tfidf` → `embeddings` (`backend/app/core/settings.py:19`); drop `paper_similarity` table (`a1b2c3d4e5f6`); delete `app/services/similarity.py` (`TfidfVectorizer`/`cosine_similarity` O(N²)), `app/models/similarity.py`, `PaperSimilarity` exports, `rebuild_similarity`/`clear_similarity`/`run_similarity_rebuild` and `similarity_pairs` branch in `app/services/ingest.py`, `--similarity-only` in `scripts/ingest_openalex.py`, `PaperSimilarity` fallback in `app/api/papers.py:212` (`/similar` now ANN-only or `[]` on SQLite), `scikit-learn`/`scipy` from `requirements.in`/`txt` (~100MB), `tests/test_similarity.py` and snapshot helpers (`tests/helpers.py:51` `add_similarity`, `tests/test_ingest_flow.py` snapshot asserts, `tests/conftest.py:72` `_PG_TABLES`). `resolve_boot_action` now `papers==0 → ingest` else `skip`. Hermetic suite shrinks `85→72`, total `90→77` (72+5 gate).
- **The "Why":** `DEC-018`'s O(N²) wall is now realized — nightly ingest is `O(Δ)` embed of touched papers only (`_apply_normalized_works` text-touch), `O(log N)` HNSW reads; `DEC-016`'s snapshot retirement was gated on Commit 7 and is now safe. BM25 (`paper_search_idx`) untouched and independent.
- **Improvement over Previous Solution:** `1.19GB` backend → lighter (scikit-learn removed), ingest `TRUNCATE+rebuild` eliminated, snapshot staleness class gone, API contract clarified (`[]` when no vector).
- **Pros:**
  - Live re-seed verified: `500 papers, 500 embeddings`, `paper_similarity` absent, `paper_search_idx` retained, `GET /papers?ranked=true` and `/papers/{id}/similar` (ANN `0.61–0.72`) both live
  - Rollback via `git revert` + `alembic downgrade` recreates empty table (one release)
- **Cons & Trade-offs:**
  - SQLite `/similar` now always `[]` without vectors (documents pg-only; no fallback)
  - `SIMILARITY_BACKEND=tfidf` env no longer has code to run (revert requires code)
- **Status:** Implemented (Commit 8: `d9b9566` — host `72 passed, 5 skipped`, container `77 passed`)

## [DEC-021] Abstract Recovery via Crossref then arXiv (No Publisher Scrape)
- **Date/Context:** 2026-08-23, Phase A (pre-implementation, choice 1A+2A: daily 20 + one-time backfill, one commit).
- **Context/What:** Recover the 57 `abstract IS NULL` papers (all have `doi`) via waterfall: `GET https://api.crossref.org/works/{doi}` → strip JATS `message.abstract`, else `GET https://export.arxiv.org/api/query?id_list={arxiv_id}` (extracted from `10.48550/arXiv.*` or OpenAlex `locations.landing_page_url`). No publisher HTML scrape per your "one time thing while ingest" scope — only those two APIs. Provenance `paper.abstract_source` (`crossref`|`arxiv`|NULL) + `abstract_recovered_at` added; recovered text re-embedded (`embed_papers_by_ids`) so BM25/HNSW see it. Daily ingest hook recovers `LIMIT 20` per run (keeps ingest +~5s), backfill script covers the 57 bulk.
- **The "Why":** `10.48550/*` DataCite DOIs are not in Crossref (arXiv's prefix) — prior verification that Crossref's `abstract` field exists for most `10.*` but misses arXiv explains the waterfall; arXiv API is the correct fallback. `301` DOI redirects observed in last ingest are `doi.org → acLanThology` permanent moves, followed to `200` by `doi_checker` (`follow_redirects=True`) and not dead — recovery uses canonical `doi.org` form, not the Location.
- **Improvement over Previous Solution:** Supersedes assessment-era "we don't scrape publishers" (tracked) with a scoped, provenance-tracked recovery that respects the no-scrape constraint.
- **Pros:**
  - Fills title-only vectors (12% of corpus) → true semantic + BM25 coverage
  - Bounded daily cost, bulk via script
  - `HttpTransport` injectable for hermetic tests
- **Cons & Trade-offs:**
  - Crossref `abstract` is JATS XML requiring strip; arXiv `summary` needs Atom parse
  - 429/backoff on both APIs possible (sleep 0.5s + retry)
- **Status:** Implemented (Phase A `f177ff3` — `76 passed, 5 skipped` host, `81` container, `57` recoverable post re-seed; live backfill 2026-08-23: `1/57` recovered via `arxiv` (`http://arxiv.org/abs/2408.16932` for dead `10.1007/9`), `56` remain title-only — waterfall low yield for this Springer/Elsevier slice as expected, daily hook `LIMIT 20` will keep trying new papers)

## [DEC-025] Scheduler Short-Retry on Failure
- **Date/Context:** 2026-08-23, post-Phase A (your recommendation: scheduler first).
- **Context/What:** `scripts/scheduler.py:71` main loop now tracks success: `run_once` returns `None` on `RuntimeError` (missing watermark) or any `run_incremental_ingest` exception; success → sleep `INGEST_INTERVAL_HOURS` (default 24h), failure → sleep `SCHEDULER_RETRY_MINUTES` (default 5m, `MIN_INTERVAL_SECONDS=60`). `backend/app/core/settings.py:17` adds `scheduler_retry_minutes: float =5.0`; `docker-compose.yml:49` exposes `SCHEDULER_RETRY_MINUTES`. Log now `sleeping X minutes until next run|retry`.
- **The "Why":** `DEC-011` noted "staleness up to full interval" on transient OpenAlex `429` (live-fire absorbed) — short retry keeps freshness without killing sidecar, still absorbs and logs.
- **Pros:** Failed cycle retries in minutes, not hours; no extra deps; `run_once` tests (`tests/test_scheduler.py:8`) still absorb missing watermark as `None`
- **Cons & Trade-offs:** tight loop on persistent failure (e.g. watermark missing forever) will retry every 5m — acceptable as it logs and never crashes; backoff not exponential (fixed 5m)
- **Status:** Implemented (`546f676` — `76 passed, 5 skipped` host, `81` container, retry 5m)

## [DEC-026] Next.js 14 → 16 + React 19 Migration (params/searchParams Promises)
- **Date/Context:** 2026-08-23, post-Phase A/scheduler/DOI.
- **Context/What:** `frontend/package.json:10` `next ^14.2.3` → `^16.1.1`, `react`/`react-dom` `^18.3.1` → `^19.2.3`, `@types/react`/`@types/react-dom` `^18` → `^19` (actual `next 16.3.3`, `react 19.2.8` via `npm ls`); `frontend/app/papers/[id]/page.tsx:7` `params: {id}` → `Promise<{id}>` + `await`, `frontend/app/page.tsx:11` `HomePage` → `async` + `await searchParams`; `tsc --noEmit` clean, `next build` (Turbopack) `Compiled successfully`, `npm audit` `0 vulnerabilities` (was 21 highs), `node:20-alpine` still satisfies `>=18.17`.
- **The "Why":** `DEC-007`'s EOL highs were in Next 14 (RSC cache-poisoning class); React 19 + Next 16 is the only fix, and `params` as Promise is the sole App Router breaking change affecting this codebase.
- **Improvement over Previous Solution:** `21 highs` → `0`, `params`/`searchParams` now future-proof for `16.x`
- **Pros:** No `next/font`/`next/image` churn; build stays `✓ Compiled successfully in 22.7s`
- **Cons & Trade-offs:** `19` peer `overriding` warning from `npm install` harmless (`deduped`); `tailwindcss 3.4` still `3.4.19` (v4 is separate)
- **Status:** Implemented (`9f14712` — `0` audit, `76` frontend `16.3.3`)

## [DEC-027] Hybrid Search RRF K=60 (Vector 10 + BM25 10 → 10, Filters After)
- **Date/Context:** 2026-08-31, Phase 4 P4-1 (hybrid, no rerank, option A filters-after).
- **Context/What:** Port `rag_web_app` `backend/api/retriever.py:135` RRF `1/(60+rank+1)` equal-weight: `GET /papers?hybrid=true&q=...` (requires `q`, `422` if `ranked` also `true`) runs dense `top 10` (`paper_embedding` `embedding <=> CAST(:qvec AS vector)` via `FastEmbedProvider` `all-MiniLM-L6-v2`) + sparse `top 10` (`paradedb.match` `paradedb.score` as in `_list_papers_ranked:77`) → RRF fuse to `10`, then `year/topic/author` filters **after** fusion (Option A) via Python on hydrated `Paper` rows (topic reload with `selectinload` when needed), paginated. `hybrid`/`ranked` separate booleans, `hybrid` degrades to ILIKE on SQLite (`test_api.py:258`), Postgres gate `test_postgres.py:61` `test_hybrid_fuses_bm25_and_vector` + `test_hybrid_filters_after` (seed `high/low_new/mid` with `FastEmbedProvider`, assert `hybrid total 3` and `year=2024 →1`). Frontend `SearchExplorer.tsx:1` + `lib/types.ts:45` + `app/page.tsx:11` add `hybrid` checkbox mutually exclusive with `ranked`, URL sync `?hybrid=true`.
- **The "Why":** `rag_web_app` `FAISS FlatL2` per-user in-memory + `BM25Okapi lower().split()` (`views.py:65`) → Radar has persistent `paradedb`/`pgvector` HNSW already; only RRF is portable. No chunking/rerank (`semantic_chunk 0.45`, `CrossEncoder`) needed for single `title+abstract` texts; skip `1` extra `fastembed` `~10ms` per search, keep `ILIKE` default `hybrid=false`.
- **Improvement over Previous Solution:** Single `hybrid` search replaces having to choose lexical *or* semantic; live `q=attention` → `hybrid 14` vs `ranked 68` vs `ILIKE 69` (top-K `14` is `10+10` RRF, not full count — documented), `year=2024&hybrid` correctly returns `1`.
- **Pros:** No schema change, `K=60` handles disparate scales without normalization, `filters after` keeps RRF pure and simple
- **Cons & Trade-offs:** `hybrid total` is fused size (≤20) not full match count; strict filters can leave page `<10` (accepted for v1); `FastEmbedProvider` failure degrades to sparse-only via `try/except`
- **Status:** Implemented (P4-1)

## [DEC-028] Bookmarks and History via localStorage (P4-2)
- **Date/Context:** 2026-08-31, Phase 4 P4-2 (localStorage v1, no backend, client-only).
- **Context/What:** `frontend/lib/bookmarks.ts` (`rr:bookmarks`/`rr:history`, `HISTORY_MAX=20`, `getBookmarkedIds`/`isBookmarked`/`toggleBookmark`/`getHistoryIds`/`pushHistory` with JATS-safe JSON parse and `isBrowser` guard) + `frontend/components/BookmarkButton.tsx` (`☆ Save`/`★ Saved`, `aria-pressed`, `preventDefault`/`stopPropagation` inside `PaperCard` link, dispatches `rr:bookmarks` event) + `frontend/components/HistoryPusher.tsx` (client `useEffect` on `params` detail page `frontend/app/papers/[id]/page.tsx:21`) + `frontend/components/PaperCard.tsx:15` bookmark beside year + `frontend/components/SearchExplorer.tsx` `★ Saved ({n})` client filter (`displayedItems` on current page, `displayedTotal` label, `Recently viewed` strip 10 when no filters, `Clear filters` resets `showSaved`, `storage` + `rr:bookmarks` listeners). No API/schema change; keys are `rr:*` to avoid collision.
- **The "Why":** Bookmarks/history are per-browser personalization with no auth — backend persistence would add user table + auth overhead for zero demo value; localStorage is instant, offline, and survives page reloads while staying zero-ops. History `MAX 20` MRU keeps strip useful without unbounded growth.
- **Improvement over Previous Solution:** Paper discovery was stateless — now saved papers filterable on current page and recently viewed `10` surfaced on empty search.
- **Pros:** Zero backend/DB migration, no cookies/auth, event-driven sync across tabs (`storage` event), graceful `try/catch` on corrupt JSON, build `✓ Compiled successfully` `tsc --noEmit` clean.
- **Cons & Trade-offs:** Bookmarks are device-local (lost on clear, not shared across devices); `Saved` filters only current page `20` (not full corpus) — full server-side saved search would need backend + auth and is deferred; history stores ids only, not titles (resolved on next fetch).
- **Status:** Implemented (P4-2)

## [DEC-029] Publisher HTML Fallback for Abstract Recovery (P4-3)
- **Date/Context:** 2026-08-31, Phase 4 P4-3 (reverses `DEC-021` no-scrape for bounded meta/section extraction).
- **Context/What:** Waterfall `abstract_recovery.py:113` `Crossref JATS → arXiv Atom → HTML`. New `app/services/publisher_extract.py:1` (`HTML_TIMEOUT=12`, `USER_AGENT`, `fetch_html_abstract` via `https://doi.org/{doi}` `follow_redirects`, `BeautifulSoup lxml` → `citation_abstract`/`dc.Description`/`og:description` meta ≥50, else `description` ≥100, else Springer `#Abs1-content`/`#Abs1-section`, Elsevier `div.abstract.author`/`section#abstract`, generic `section.abstract` ≥80, whitespace-normalized `<50` reject; `source_for_doi` `10.1007→springer`/`10.1016→elsevier`/`html_generic`). `recover_abstract_for_paper` lazy imports HTML step after arXiv miss; `recover_missing_abstracts` still `limit=20` + `0.5s` polite. Deps `beautifulsoup4==4.12.3`/`lxml==5.3.0`/`soupsieve==2.5` via `requirements.in:10`.
- **The "Why":** `56/57` title-only from `DEC-021` are Springer/Elsevier (`10.1007`/`10.1016`) whose `message.abstract` is null and arXiv `landing_page_url` absent — previous `1/57` via arXiv was the only recoverable; HTML `citation_abstract` meta (Highwire Press) is stable without JS and covers both publishers.
- **Improvement over Previous Solution:** Title-only `56` now recoverable without paywall bypass beyond public meta; recovered rows still `abstract_source`/`recovered_at` + `embed_papers_by_ids` so BM25/HNSW see text.
- **Pros:** No migration (`String(16)` fits `springer`/`html_generic`), hermetic `MockTransport` HTML tests `5` (`test_fetch_html_*` + `test_recover_html_source_tagged`), safe fallback `None` on `403`/`404`, circular-safe lazy import.
- **Cons & Trade-offs:** HTML is brittle (publisher redesign → `None` again, safe); `lxml` wheel `~5MB`; daily ingest `limit=20` adds `~10s` worst (still bounded); `doi.org` redirect required (no stored `landing_page_url` in `paper` model).
- **Status:** Implemented (P4-3 — `79 passed, 7 skipped` host, `5` new hermetic)

## [DEC-030] P5-A Full-Corpus Saved Search via ids (Option A)
- **Date/Context:** 2026-09-03, Phase 5 P5-A (your picks: Option A intersect-then-rank, 2A fetch titles, 3A saved in URL, 4A merge with replace checkbox).
- **Context/What:** `GET /papers?ids=1,2,3` (`_parse_ids` in `papers.py:70` — strip, int, dedupe, cap `100`, ignore invalid, empty → empty). AND-combined in legacy (`Paper.id.in_`), ranked (`AND p.id IN`), and hybrid (post-fuse intersect). Frontend `PaperQuery.ids` + `buildQuery` passthrough, `SearchExplorer` server `ids=[...bookmarkedIds]` with server `total`, `saved=true` URL persist, history `10` titles via `fetchPaper` batch (`allSettled`, skip `404`), Export (`Blob`) + Import (`parseBookmarksJson` + `replace` checkbox), `clearHistory`. Detail page gains `BookmarkButton` beside year; `BookmarkButton` syncs via `rr:bookmarks` + `storage`; `PaperCard` outer `<a>` → `<div>` with inner title link.
- **The "Why":** `DEC-028` Saved filtered only current page `20` with `displayedTotal` label — full-corpus search needed server support without auth. Client-only plus `ids` keeps zero ops while fixing the gap.
- **Pros:** No migration, no auth, `5` hermetic `ids` tests, `tsc` + `build` green, cross-tab sync, export round-trip.
- **Cons & Trade-offs:** URL caps at `100` ids (export file for larger); `ids` with `ranked/hybrid` still requires `q` (`422` otherwise); history titles cost up to `10` fetches on home load.
- **Status:** Implemented (P5-A — `84 passed, 7 skipped` host, `91` container, `008f29d`)

## [DEC-031] P5-B Fusion-Window Hybrid with Filters-Before plus Eval Scorecard (1A-fixed, 2A, 3A, 4A-off)
- **Date/Context:** 2026-09-03, Phase 5 P5-B (your picks: 1A honest window count, 2A fixed seed, 3A info-only, 4A rerank off).
- **Context/What:** Hybrid was dense `10` + sparse `10` → RRF `K=60` → filters-after Python → `total=len(filtered)` (`≤20`, page `2` empty). Now dense `100` + sparse `100` (`DENSE_K/SPARSE_K`) with shared filters-before fragment in SQL (`year/topic/author/ids`, mirroring ranked), `total=len(fused)` (`≤200`, 10x wider window), hydrate page window in RRF order via single query, no Python `_keep`, no topic reload. RRF `K=60` unchanged. Live-fire correction during build: first cut used query-blind `dense_all LIMIT 1000` for `total` and returned `hybrid total 500` for every query — fixed to `total=len(fused)` (2 queries saved per search). Eval is `tests/fixtures/qrels.jsonl` (`8` queries `q01-q08`, substring relevance, no live ids) + `scripts/eval_search.py` (live-HTTP default, `MRR/NDCG@10/recall@20`, exit `0` info-only, SQLite-degrade warning). Rerank stays off (`fastembed TextCrossEncoder` would be the fit, `torch` rejected).
- **The "Why":** `hybrid 14 vs ranked 68 vs ILIKE 69` totals confused users and short pages hid matches under strict filters. Fusion-window plus over-fetch fixes pagination honesty within what vector search can promise (no natural full count — every paper has a distance); scorecard proves ranking without guessing.
- **Pros:** No schema change, `422` guards unchanged, SQLite degrade unchanged, `2` fewer SQL queries per search than first cut, `2` new gate tests (window-count + deep pagination), `.gitignore` exception for fixture only.
- **Cons & Trade-offs:** Larger fan-out per query (`100+100` vs `10+10`); `total` stays window-bound (`≤200`, not full corpus count — documented); eval thresholds stay off until `3-5` baselines.
- **Status:** Implemented (P5-B — `84 passed, 9 skipped` host, `93` container, eval `legacy 0.41/0.47/0.29 wins 5 vs ranked 0.625/0.62/0.53 wins 7 vs hybrid 0.625/0.62/0.51 wins 7`)

## [DEC-032] P5-C Reliability: DLQ plus Retry Polish plus Backoff plus Metrics (Rate Limit/Auth Deferred)
- **Date/Context:** 2026-09-04, Phase 5 P5-C (your picks: table DLQ, shared retry yes, backfill fix yes, metrics now, rate limit later, auth only if needed; one commit for the step).
- **Context/What:** Failures were log-only (`_drop_unresolvable_dois`, `normalize_skip`, `scheduler.run_once`, CLI top level — no DLQ anywhere). New `IngestDlq` model (`models/ingest_dlq.py`, `String(16)`-safe generic `JSON`, indexes on `status`/`openalex_id`) + migration `c8d9e0f1a2b3` (head after `b2c3d4e5f6a7`, SQLite-compatible) + hooks in `_normalize_fetched` (`normalize_skip`) and `_drop_unresolvable_dois` (`unresolvable_doi`, same-session rows riding the run commit, counters/logs unchanged, no `IngestReport` break) + `scripts/retry_dlq.py` (dry-run marking `pending→retried`, no refetch in v1). Shared `services/http_retry.py` (stdlib only: `RETRYABLE={429,502,503,504}`, `parse_retry_after` delta-date capped `60`, `compute_sleep=min(cap,max(exp,ra)+jitter)`, name-based exception check) now drives `openalex._get` (fail-fast on `400/401/403/404/422`, keeps legacy `500` retry for the `500x3` test), `abstract_recovery` + `publisher_extract` (thin wrappers, now also retry `500/502/503`). Scheduler tracks `consecutive_failures` with `retry*2^min(n,5)` capped by new `scheduler_backoff_max_minutes=60` plus `uniform(0,30s)` jitter; new `recovery_limit=20` setting documents the daily hook cap. Backfill pagination fixed from `offset=attempted` skip bug to `offset=0` shrinking-set loop with `consecutive_zeros>=2` exit. Metrics is zero-dep `GET /metrics` in `main.py` (uptime + paper count, `text/plain`, `200` even when DB down, `/health` untouched, no new wheel).
- **The "Why":** Dropped works were unreproducible after log rotation; OpenAlex over-retried `4xx` while ignoring `Retry-After`; fixed `5m` retry hammered outages; backfill skipped shifted rows; ops had no scrape target. Each fix is small and keeps current contracts (absorb-and-log sidecar, conservative DOI keep, polite pauses).
- **Pros:** Queryable failures with replay path; polite + cheaper retries; no-skip backfill; scrape target with zero image growth; `6` new hermetic tests (`test_ingest_dlq` + `test_http_retry`).
- **Cons & Trade-offs:** Run-level flush errors still bubble (not captured, by design); `retry_dlq` v1 marks rather than refetches; metrics has no Prometheus service in compose yet; rate limit (`slowapi`/`redis`) and auth (key/JWT) deferred as agreed.
- **Status:** Implemented (P5-C — `90 passed, 9 skipped` host, `99` container, `1f0fa84`)

## [DEC-033] Frontend Redesign as Citation Ledger (frontend-design Skill)
- **Date/Context:** 2026-09-04, frontend upgrade (your detailed plan: visual/UX only, skill-first, checkpointed design lead, five file-isolated subagents).
- **Context/What:** Old UI matched the skill's SaaS-card-kit tell (uniform `rounded-lg` + `shadow-sm` cards, indigo + emerald, flat `slate-50`, default sans, gray empty text, empty `theme.extend`). Design lead phase locked tokens first (`tailwind.config.ts`: `paper/paper-deep/ink/signal/signal-dark/sage/rule`; Newsreader + Inter via `next/font`; `globals.css` base with global signal focus ring, `tnum`, single shimmer) and wrote `design/brief.md` (tokens, type roles, grid, 375px row-collapse contract shared by card and detail rows, shared states, motion cap, a11y floor, do/don't) before any subagent started. Five parallel subagents (search shell, card + star, pagination a11y, detail + 404, loading skeletons) read the brief first and invented nothing. Integration fixed one palette drift (`app/page.tsx` shell) and wired `rank` into `PaperCard`. Deliverables: `design/brief.md`, `design/critique-notes.md`, `design/screenshots/` (home/detail at 1440 + true-375 via puppeteer).
- **The "Why":** Tool-like credibility for researchers scanning at speed, grounded in citation-index conventions (ruled rows with rank numerals — numbering is legitimate because ranked results are a true sequence). One radar motif only (header scan-rule tick). Scope held: zero changes to API client, types, bookmarks logic, fetching, debounce, URL sync, or export/import flow.
- **Pros:** Distinct identity without new deps; hierarchy from rules + numerals instead of shadows; a11y raised (`aria-current`, labeled Prev/Next, real import button, skeletons, global focus ring); `tsc` + `build` green throughout.
- **Cons & Trade-offs:** Logo mark still carries old blue artwork; `sage` at 12px unmetered; remaining states unshot (loading/empty/error/history, 768px); Chrome CLI `--window-size=375` screenshots show false overflow (minimum-window crop) — trust puppeteer viewports for narrow widths.
- **Status:** Implemented (`79dbf6a` + `1350643` screenshots)

## [DEC-034] Memoized URL-Sync State Stops Replace Render Loop
- **Date/Context:** 2026-09-04, found during redesign verification (tab title flicker report, backend logs clean).
- **Context/What:** `SearchExplorer` built `compact` as a fresh object literal every render with `useEffect(syncUrl, [compact, syncUrl])` — every render fired `router.replace`, every replace scheduled another render. Measured `880` replaces in 12s idle via `history.replaceState` counter; tab loading state flashed continuously. Fix wraps `compact` in `useMemo` on primitives (plus missing `useMemo` import) — `2` replaces over the same window, title steady. Predates the redesign; noticed once the live tab got real use.
- **Pros:** One-line-class fix, zero behavior change, `tsc` green, live-verified before/after.
- **Cons & Trade-offs:** Fetch effect still keys on `bookmarkedIds` Set identity (refetch on bookmark events — needed for saved mode, accepted).
- **Status:** Implemented (`ed65f0b`)

## [DEC-035] P5_2-a Library Upgrades (bs4, lxml, Node 22, Python 3.13, sqlalchemy guard)
- **Date/Context:** 2026-09-04, Phase 5 part 2 step a (your call: do all four slices, minimal blast radius).
- **Context/What:** Two parallel isolated tracks. Backend: `beautifulsoup4 4.12.3→4.15.0` + `soupsieve 2.5→2.9.2` + `lxml 5.3.0→6.1.3` (exact pins in `requirements.in/txt`, hand-edited, no pip-tools on host), `sqlalchemy>=2.0,<3.0` → `>=2.0,<2.1` (`txt` stays `2.0.52`), `python:3.12-slim` → `python:3.13-slim` (all pinned wheels verified with cp313 builds, bake layer clean, container `3.13.15`). Frontend: `node:20-alpine` (EOL) → `node:22-alpine`, `@types/node ^20→^22` (`22.20.1`), everything else locked (`next 16.3.3`, `react 19.2.8`, `ts 5.9.3`, `tailwind 3.4.19`). Lead aggregated CI (`python 3.12→3.13`, `node 20→22`) plus README stack.
- **The "Why":** Parsers were 2 majors stale, Node 20 past EOL, and the open `<3.0` range would auto-pull sqlalchemy `2.1` final one day. Python `3.13` was the risky slice (suspects `onnxruntime`/`numpy`) — pip resolved cleanly, so it landed instead of aborting.
- **Pros:** Zero behavior change (no API, UI, or ranking diffs); old `strip_cdata` deprecation warning gone; `npm audit 0`, `tsc` + `build` green on both stacks; host `90 passed, 9 skipped`, container `99 passed`, fastembed import smoke OK.
- **Cons & Trade-offs:** `requirements.txt` hand-pinned without `pip-compile` (pip-tools absent on host — recompile on next dep change); `3.13.15` floats on `3.13-slim` rebuilds as before.
- **Status:** Implemented (P5_2-a)

---

## [DEC-036] P5_2-b Redesign Tails (Logo, Contrast, Screenshots, History Fix)
- **Date/Context:** 2026-09-04, Phase 5 part 2 step b (your picks: full redraw, Newsreader wordmark, all 9 states, one commit; descriptor `Every paper, on the record.`).
- **Context/What:** Contrast metered (`sage` on `paper` = 4.97, AA pass) plus two 12px action labels defaulted to ink (`SearchExplorer.tsx:451,465`). Logo adapted from owner draft `new_logo/logo-v3.svg` (untracked source): token remap, depth filters kept per owner, solid-ink Newsreader wordmark, sage sentence-case descriptor, simplified mark-only cut (no tick/inner ring at 32px), PNG regenerated at same 1600x500 contract. Screenshot sweep via puppeteer true viewports added 8 states (`empty-filtered/saved`, `error` via API-only abort, `history-visible`, `null-abstract` id 10, `404`, 768 home/detail); honestly skipped `loading` (SSR streams instantly, skeleton never paints) and `similar-failed` (server-rendered, identical to empty case). Sweep found a real bug: history resolver used server `fetchPaper` (`backend:8000` unreachable in browsers) so pills never resolved — new `fetchPaperClient` on the public base URL, detail keeps server fetch, live-verified with titles.
- **Pros:** Closed every critique-notes item except square favicon + focus-ring confirm + pill wrap (deferred as follow-ups); zero behavior change otherwise; `tsc` + `build` green.
- **Cons & Trade-offs:** Favicon stays a wide lockup canvas (tab-icon suboptimal, needs square variant to fix); `new_logo/` drafts left untracked by design.
- **Status:** Implemented (P5_2-b)

## [DEC-037] P5_2-c Eval Close-Out (New Job, Fixture Seed, Wired Exits, Soft)
- **Date/Context:** 2026-09-04, Phase 5 part 2 step c (your picks: new job, fixture seed, wire now, block after baselines).
- **Context/What:** Eval script exited `0` no matter what (even dead backend) and CI had no eval step. New `eval` CI job with own `paradedb` service (no `needs:`, parallel, `continue-on-error` with drop-the-line-to-enforce comment, table artifact 30d). Fixture seeder `scripts/seed_eval.py` writes 12 `EVAL-*` papers (no live-id drift, idempotent skip, `--drop-first` for fresh DBs) instead of a 5–8 min live ingest. `--fail-under-mrr` now really exits `1` plus new `--fail-under-ndcg`; defaults stay exit-`0` so the job is advisory until bands are learned.
- **Pros:** Per-PR signal without blocking anyone; zero image/storage cost (stdlib + httpx only, 2 KB artifact); live 500-paper corpus never touched (verified: seeder `main()` never ran locally).
- **Cons & Trade-offs:** ~2 extra CI minutes per run; fixture numbers are comparative, not live-corpus truth; blocking flip still needs its own decision after baselines.
- **Status:** Implemented (P5_2-c)

## [DEC-038] P5_2-d Rate Limit plus Optional API Key (Full Login Skipped)
- **Date/Context:** 2026-09-04, Phase 5 part 2 step d (your picks: rate limit stays, API key as described, no Google/GitHub/email login).
- **Context/What:** No auth layer existed at all. New `app/core/rate_limit.py` (stdlib only: sliding 60s window, `threading.Lock`, per-IP key, `check` returns retry seconds, `clear` for tests) wired as middleware in `create_app` covering `/papers` routes only (`/health`, `/metrics`, docs exempt); over cap returns `429` with `Retry-After`. New `require_api_key` in `app/api/deps.py` (`secrets.compare_digest`, empty setting means open) attached as router-level `Depends` on the papers router (list, detail, similar); health and metrics stay public. Settings add `rate_limit_per_minute=60` (`0` disables) and `api_key=""`; compose passes both through with matching defaults. The browser frontend calls the backend directly, so a shipped key is network-visible; real browser enforcement still needs a server proxy, documented as out of scope.
- **The "Why":** Rate limit is the piece that actually protects the DB from scrapers. API key alone on a read-only public corpus is theater without a proxy, so it ships optional and off by default rather than forced on day one. Full user login was dropped because saved state lives client-side and syncs nowhere.
- **Pros:** Zero new deps, zero image growth, zero migrations; `6` new hermetic tests (cap + headers + exempt routes, open-by-default + 401 paths); autouse fixture keeps the shared-IP TestClient suite green.
- **Cons & Trade-offs:** In-memory store is per-process (fine at one replica, wrong at many — redis would be the next step); key rotation is manual with no UI; frontend sends no key until a proxy exists.
- **Status:** Implemented (P5_2-d)

## Pending Queue (logged, not yet started)
- *None — Phase 3 (Commits 1–8), Phase A abstract recovery, scheduler retry, DOI allowlist, Next.js 16, P4-1 hybrid, P4-2 bookmarks/history, P4-3 HTML fallback, P5-A saved via ids, P5-B window hybrid plus eval, P5-C reliability, frontend redesign, and P5_2-a/b/c upgrades all landed. P5_2-d rate limit plus API key landed; full user login skipped by decision. Remaining: P5_2-e docs final push.*
