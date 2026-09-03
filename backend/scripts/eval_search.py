#!/usr/bin/env python3
"""Minimal eval harness: legacy vs ranked vs hybrid (P5-B2, info-only).

Compares the three ``GET /papers`` dispatcher paths from ``app/api/papers.py``:

- legacy:  ``GET /papers?q=...``
- ranked:  ``GET /papers?q=...&ranked=true``   (BM25 on Postgres, 422 without q)
- hybrid:  ``GET /papers?q=...&hybrid=true``   (RRF dense+sparse, 422 without q)

Relevance is substring matching (stable, no live ids — 2A fixed logic):
a hit is relevant iff ``title + abstract`` contains ANY of the qrel's
``relevant_substrings`` (case-insensitive). Unjudged / non-matching = 0.

Metrics per query per mode (page_size 20):

- MRR: 1/rank of first relevant, else 0.
- NDCG@10: binary DCG@10 / IDCG@10 where IDCG is built from the count of
  relevant retrieved for that query+mode capped at 10 (standard when the
  corpus-wide relevant total is unknown). 0 when nothing relevant retrieved.
- recall@20 (pooled): relevant_retrieved@20 / union_relevant@20, where the
  denominator is the number of DISTINCT relevant doc ids in the union of the
  three modes' top-20 for that query. 0 when the pool is empty. This is a
  comparative proxy — true corpus recall is unknowable without full judgments.
- wins: # queries where the mode ties for best NDCG@10.

Modes:

- live (default): HTTP against --base-url (default http://localhost:8000)
  with httpx, timeout 10s. Handles 422 (e.g. ranked/hybrid without q —
  treated as empty with a warning).
- testclient-postgres: in-process fastapi TestClient wired to DATABASE_URL
  (must be postgresql://... and reachable). Warns + exits 0 when unavailable.
  On SQLite the dispatcher degrades hybrid==ranked==legacy, so this script
  warns when all three orderings are identical (SQLite degrade signal).

Exit code is ALWAYS 0 (3A info-only). --fail-under-mrr is accepted for
forward-compat but only prints a warning, never fails.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

import httpx

MODES = ("legacy", "ranked", "hybrid")
NDCG_K = 10
RECALL_N = 20


def load_qrels(path: Path) -> list[dict]:
    qrels: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"WARNING: skipping {path}:{lineno}: bad JSON ({exc})", file=sys.stderr)
                continue
            if not all(k in entry for k in ("qid", "q", "relevant_substrings")):
                print(f"WARNING: skipping {path}:{lineno}: missing qid/q/relevant_substrings", file=sys.stderr)
                continue
            entry.setdefault("year", None)
            entry.setdefault("author", None)
            qrels.append(entry)
    return qrels


def is_relevant(item: dict, substrings: list[str]) -> bool:
    hay = f"{item.get('title') or ''} {item.get('abstract') or ''}".lower()
    return any(s.lower() in hay for s in substrings if s)


def mrr(rels: list[int]) -> float:
    for i, r in enumerate(rels):
        if r:
            return 1.0 / (i + 1)
    return 0.0


def dcg_at_k(rels: list[int], k: int) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels[:k]) if r)


def ndcg_at_k(rels: list[int], k: int = NDCG_K) -> float:
    n_rel = sum(1 for r in rels[:k] if r)
    if n_rel == 0:
        return 0.0
    ideal = sum(1.0 / math.log2(i + 2) for i in range(min(n_rel, k)))
    if ideal == 0:
        return 0.0
    return dcg_at_k(rels, k) / ideal


def build_params(qrel: dict, mode: str, page_size: int) -> dict:
    params: dict[str, object] = {"q": qrel["q"], "page": 1, "page_size": page_size}
    if qrel.get("year") is not None:
        params["year"] = qrel["year"]
    if qrel.get("author"):
        params["author"] = qrel["author"]
    if mode == "ranked":
        params["ranked"] = "true"
    elif mode == "hybrid":
        params["hybrid"] = "true"
    return params


def fetch_live(
    http: httpx.Client, qrel: dict, mode: str, page_size: int, warnings: list[str]
) -> list[dict]:
    params = build_params(qrel, mode, page_size)
    try:
        resp = http.get("/papers", params=params)  # type: ignore[arg-type]
    except httpx.TimeoutException:
        warnings.append(f"{qrel['qid']}/{mode}: timeout, treated as empty")
        return []
    except httpx.HTTPError as exc:
        warnings.append(f"{qrel['qid']}/{mode}: HTTP error {exc}, treated as empty")
        return []
    if resp.status_code == 422:
        warnings.append(f"{qrel['qid']}/{mode}: 422 (e.g. ranked/hybrid requires q), treated as empty")
        return []
    if resp.status_code != 200:
        warnings.append(f"{qrel['qid']}/{mode}: status {resp.status_code}, treated as empty")
        return []
    try:
        body = resp.json()
    except ValueError:
        warnings.append(f"{qrel['qid']}/{mode}: non-JSON body, treated as empty")
        return []
    items = body.get("items", [])
    return items if isinstance(items, list) else []


def make_pg_test_client() -> tuple[object, list[str]]:
    """Build a fastapi TestClient bound to DATABASE_URL (postgres only).

    Returns (client, warnings). Raises RuntimeError with a human message when
    postgres is unavailable — caller converts to warning + empty result.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import NullPool

    warnings: list[str] = []
    try:
        from app.api.deps import get_db
        from app.core.settings import get_settings
        from app.main import app
    except Exception as exc:  # pragma: no cover - import path issue
        raise RuntimeError(f"cannot import app ({exc})")

    try:
        url = os.getenv("DATABASE_URL") or get_settings().database_url
    except Exception as exc:
        raise RuntimeError(f"cannot resolve DATABASE_URL ({exc})")
    if not url.startswith("postgresql"):
        raise RuntimeError(f"testclient-postgres needs postgresql DATABASE_URL, got {url!r}")
    engine = create_engine(url, poolclass=NullPool, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        engine.dispose()
        raise RuntimeError(f"postgres not reachable at {url}: {exc}")
    Testing = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _override():
        s = Testing()
        try:
            yield s
        finally:
            s.close()

    from fastapi.testclient import TestClient

    app.dependency_overrides[get_db] = _override  # type: ignore[index]
    client = TestClient(app)
    # stash cleanup so caller can clear overrides + dispose
    client.headers.update({})  # no-op to keep type simple
    return (client, engine)


def evaluate(
    results: dict[str, dict[str, list[dict]]], qrels: list[dict]
) -> tuple[dict[str, dict[str, float]], dict[str, int]]:
    """Aggregate mean MRR / NDCG@10 / pooled recall@20 per mode + wins."""
    agg: dict[str, dict[str, float]] = {m: {"mrr": 0.0, "ndcg": 0.0, "recall": 0.0} for m in MODES}
    wins: dict[str, int] = {m: 0 for m in MODES}
    n = max(1, len(qrels))
    for qrel in qrels:
        qid = qrel["qid"]
        subs = qrel.get("relevant_substrings", [])
        per_mode_rels: dict[str, list[int]] = {}
        per_mode_rel_ids: dict[str, set] = {}
        for mode in MODES:
            items = results.get(qid, {}).get(mode, [])
            rels = [1 if is_relevant(it, subs) else 0 for it in items[:RECALL_N]]
            per_mode_rels[mode] = rels
            per_mode_rel_ids[mode] = {
                it.get("id") for it, r in zip(items[:RECALL_N], rels) if r and it.get("id") is not None
            }
        pool = set().union(*per_mode_rel_ids.values()) if per_mode_rel_ids else set()
        denom = len(pool) if pool else 0
        ndcgs: dict[str, float] = {}
        for mode in MODES:
            rels = per_mode_rels[mode]
            m = mrr(rels)
            nd = ndcg_at_k(rels, NDCG_K)
            ndcgs[mode] = nd
            rec = (len(per_mode_rel_ids[mode]) / denom) if denom else 0.0
            agg[mode]["mrr"] += m
            agg[mode]["ndcg"] += nd
            agg[mode]["recall"] += rec
        best = max(ndcgs.values()) if ndcgs else 0.0
        for mode in MODES:
            if ndcgs[mode] == best:
                wins[mode] += 1
    for mode in MODES:
        agg[mode]["mrr"] /= n
        agg[mode]["ndcg"] /= n
        agg[mode]["recall"] /= n
    return agg, wins


def detect_degrade(results: dict[str, dict[str, list[dict]]], qrels: list[dict]) -> bool:
    """True when ranked==hybrid==legacy ordering for every query (SQLite degrade)."""
    if not qrels:
        return False
    for qrel in qrels:
        qid = qrel["qid"]
        orders = []
        for mode in MODES:
            orders.append([it.get("id") for it in results.get(qid, {}).get(mode, [])])
        if not (orders[0] == orders[1] == orders[2]):
            return False
    return True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_qrels = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "qrels.jsonl"
    ap = argparse.ArgumentParser(description="Compare legacy vs ranked vs hybrid search (info-only, exit 0).")
    ap.add_argument("--qrels", default=str(default_qrels), help="path to qrels.jsonl (default: tests/fixtures/qrels.jsonl)")
    ap.add_argument("--base-url", default="http://localhost:8000", help="base URL for --mode live (default: http://localhost:8000)")
    ap.add_argument(
        "--mode",
        choices=["live", "testclient-postgres"],
        default="live",
        help="live: HTTP via httpx; testclient-postgres: in-process TestClient on DATABASE_URL",
    )
    ap.add_argument("--page-size", type=int, default=20, help="page_size per request (default: 20)")
    ap.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds (default: 10)")
    ap.add_argument(
        "--fail-under-mrr",
        type=float,
        default=None,
        help="optional threshold; info-only warning when all modes score below it (exit stays 0)",
    )
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    qrels_path = Path(args.qrels)
    if not qrels_path.is_file():
        print(f"ERROR: qrels not found: {qrels_path}", file=sys.stderr)
        return 0
    qrels = load_qrels(qrels_path)
    if not qrels:
        print("WARNING: no qrels loaded; nothing to evaluate", file=sys.stderr)
        print("| mode | MRR | NDCG@10 | recall@20 | wins |")
        print("|---|---|---|---|---|")
        return 0

    warnings: list[str] = []
    results: dict[str, dict[str, list[dict]]] = {q["qid"]: {} for q in qrels}

    if args.mode == "live":
        with httpx.Client(base_url=args.base_url, timeout=args.timeout) as http:
            for qrel in qrels:
                for mode in MODES:
                    results[qrel["qid"]][mode] = fetch_live(http, qrel, mode, args.page_size, warnings)
    else:  # testclient-postgres
        try:
            client_and_engine = make_pg_test_client()
        except RuntimeError as exc:
            print(f"WARNING: {exc}; cannot evaluate testclient-postgres, reporting empty", file=sys.stderr)
            for qrel in qrels:
                for mode in MODES:
                    results[qrel["qid"]][mode] = []
            agg, wins = evaluate(results, qrels)
            print("| mode | MRR | NDCG@10 | recall@20 | wins |")
            print("|---|---|---|---|---|")
            for mode in MODES:
                print(f"| {mode} | {agg[mode]['mrr']:.4f} | {agg[mode]['ndcg']:.4f} | {agg[mode]['recall']:.4f} | {wins[mode]} |")
            return 0
        client, engine = client_and_engine  # type: ignore[misc]
        try:
            for qrel in qrels:
                for mode in MODES:
                    params = build_params(qrel, mode, args.page_size)
                    try:
                        resp = client.get("/papers", params=params)  # type: ignore[union-attr]
                    except Exception as exc:
                        warnings.append(f"{qrel['qid']}/{mode}: TestClient error {exc}, treated as empty")
                        results[qrel["qid"]][mode] = []
                        continue
                    if resp.status_code == 422:
                        warnings.append(f"{qrel['qid']}/{mode}: 422, treated as empty")
                        results[qrel["qid"]][mode] = []
                    elif resp.status_code != 200:
                        warnings.append(f"{qrel['qid']}/{mode}: status {resp.status_code}, treated as empty")
                        results[qrel["qid"]][mode] = []
                    else:
                        try:
                            items = resp.json().get("items", [])
                        except ValueError:
                            warnings.append(f"{qrel['qid']}/{mode}: non-JSON, treated as empty")
                            items = []
                        results[qrel["qid"]][mode] = items if isinstance(items, list) else []
        finally:
            try:
                from app.main import app as _app

                _app.dependency_overrides.clear()
            except Exception:
                pass
            try:
                engine.dispose()  # type: ignore[union-attr]
            except Exception:
                pass

    agg, wins = evaluate(results, qrels)

    print("| mode | MRR | NDCG@10 | recall@20 | wins |")
    print("|---|---|---|---|---|")
    for mode in MODES:
        print(f"| {mode} | {agg[mode]['mrr']:.4f} | {agg[mode]['ndcg']:.4f} | {agg[mode]['recall']:.4f} | {wins[mode]} |")

    if detect_degrade(results, qrels):
        print(
            "WARNING: ranked==hybrid==legacy on all queries — likely SQLite degrade "
            "(non-Postgres dialect falls back to ILIKE) or an empty corpus.",
            file=sys.stderr,
        )
    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

    if args.fail_under_mrr is not None:
        best = max(agg[m]["mrr"] for m in MODES)
        if best < args.fail_under_mrr:
            print(
                f"WARNING: best MRR {best:.4f} < --fail-under-mrr {args.fail_under_mrr} "
                "(info-only, exit stays 0)",
                file=sys.stderr,
            )

    return 0  # info-only by design


if __name__ == "__main__":
    raise SystemExit(main())
