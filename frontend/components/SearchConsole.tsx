"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import DetectionRow from "@/components/DetectionRow";
import Pagination from "@/components/Pagination";
import Select from "@/components/Select";
import { fetchPaperClient, fetchPapers, TOPIC_SLUGS, YEARS } from "@/lib/api";
import {
  clearHistory,
  exportBookmarksJson,
  getBookmarkedIds,
  getHistoryIds,
  importBookmarks,
  parseBookmarksJson,
} from "@/lib/bookmarks";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import type { PaperListResponse } from "@/lib/types";

const PAGE_SIZE = 20;
const DEBOUNCE_MS = 300;

const MODES = [
  { key: "standard", label: "Standard" },
  { key: "ranked", label: "Ranked (BM25)" },
  { key: "hybrid", label: "Hybrid (RRF)" },
] as const;

type ModeKey = (typeof MODES)[number]["key"];

const labelCls = "block font-mono text-[11px] tracking-[0.18em] text-haze";
const fieldCls =
  "mt-1.5 border border-line bg-well px-2.5 py-2 text-sm leading-[1.55] text-ice placeholder:text-haze/70";

interface SearchConsoleProps {
  initialQ: string;
  initialYear: string;
  initialTopic: string;
  initialAuthor: string;
  initialPage: number;
  initialRanked?: boolean;
  initialHybrid?: boolean;
  initialSaved?: boolean;
}

export default function SearchConsole({
  initialQ,
  initialYear,
  initialTopic,
  initialAuthor,
  initialPage,
  initialRanked = false,
  initialHybrid = false,
  initialSaved = false,
}: SearchConsoleProps) {
  const router = useRouter();
  const pathname = usePathname();

  const [q, setQ] = useState(initialQ);
  const [year, setYear] = useState(initialYear);
  const [topic, setTopic] = useState(initialTopic);
  const [author, setAuthor] = useState(initialAuthor);
  const [page, setPage] = useState(initialPage);
  const [ranked, setRanked] = useState(initialRanked);
  const [hybrid, setHybrid] = useState(initialHybrid);
  const [showSaved, setShowSaved] = useState(initialSaved);
  const [bookmarkedIds, setBookmarkedIds] = useState<Set<number>>(new Set());
  const [historyIds, setHistoryIds] = useState<number[]>([]);
  const [historyDetails, setHistoryDetails] = useState<
    Record<number, { title: string; year: number }>
  >({});
  const [historyResolved, setHistoryResolved] = useState(false);
  const [replaceImport, setReplaceImport] = useState(false);
  const [importMessage, setImportMessage] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const [result, setResult] = useState<PaperListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const debouncedQ = useDebouncedValue(q, DEBOUNCE_MS);

  const mode: ModeKey = hybrid ? "hybrid" : ranked ? "ranked" : "standard";

  const applyState = useCallback(
    (next: { q?: string; year?: string; topic?: string; author?: string; page?: number; ranked?: boolean; hybrid?: boolean }) => {
      setQ((v) => next.q ?? v);
      setYear((v) => next.year ?? v);
      setTopic((v) => next.topic ?? v);
      setAuthor((v) => next.author ?? v);
      setPage((v) => next.page ?? v);
      if (next.ranked !== undefined) setRanked(next.ranked);
      if (next.hybrid !== undefined) setHybrid(next.hybrid);
    },
    []
  );

  const syncUrl = useCallback(
    (value: { q: string; year: string; topic: string; author: string; page: number; ranked: boolean; hybrid: boolean; showSaved: boolean }) => {
      const search = new URLSearchParams();
      if (value.q) search.set("q", value.q);
      if (value.year) search.set("year", value.year);
      if (value.topic) search.set("topic", value.topic);
      if (value.author) search.set("author", value.author);
      if (value.page > 1) search.set("page", String(value.page));
      if (value.ranked) search.set("ranked", "true");
      if (value.hybrid) search.set("hybrid", "true");
      if (value.showSaved) search.set("saved", "true");
      const qs = search.toString();
      router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
    },
    [pathname, router]
  );

  // Memoized: a fresh object literal every render would re-fire the
  // syncUrl effect after EVERY render, and each router.replace schedules
  // another render — an infinite replace loop that flashes the tab
  // loading state. Primitives keep the identity stable.
  const compact = useMemo(
    () => ({ q: debouncedQ, year, topic, author, page, ranked, hybrid, showSaved }),
    [debouncedQ, year, topic, author, page, ranked, hybrid, showSaved]
  );

  useEffect(() => {
    const refresh = () => {
      setBookmarkedIds(getBookmarkedIds());
      setHistoryIds(getHistoryIds());
    };
    refresh();
    window.addEventListener("rr:bookmarks", refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener("rr:bookmarks", refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  // History: batch-resolve first 10 ids to title+year (skip 404s).
  useEffect(() => {
    const ids = historyIds.slice(0, 10);
    if (ids.length === 0) {
      setHistoryDetails({});
      setHistoryResolved(true);
      return;
    }
    let cancelled = false;
    setHistoryResolved(false);
    Promise.allSettled(ids.map((id) => fetchPaperClient(String(id)))).then((outcomes) => {
      if (cancelled) return;
      const next: Record<number, { title: string; year: number }> = {};
      outcomes.forEach((r, i) => {
        if (r.status === "fulfilled") {
          next[ids[i]] = { title: r.value.title, year: r.value.publication_year };
        }
      });
      setHistoryDetails(next);
      setHistoryResolved(true);
    });
    return () => {
      cancelled = true;
    };
  }, [historyIds]);

  // Saved view filters the full corpus server-side via the ids param.
  useEffect(() => {
    if (showSaved && bookmarkedIds.size === 0) {
      setResult({ items: [], total: 0, page, page_size: PAGE_SIZE });
      setLoading(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    let cancelled = false;

    const idsParam = showSaved ? [...bookmarkedIds].join(",") : undefined;
    fetchPapers({
      q: debouncedQ,
      year,
      topic,
      author,
      page,
      page_size: PAGE_SIZE,
      ranked: ranked || undefined,
      hybrid: hybrid || undefined,
      ids: idsParam,
    })
      .then((data) => {
        if (!cancelled) setResult(data);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Request failed");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [debouncedQ, year, topic, author, page, ranked, hybrid, showSaved, bookmarkedIds]);

  useEffect(() => {
    syncUrl(compact);
  }, [compact, syncUrl]);

  const handleExport = useCallback(() => {
    const json = exportBookmarksJson();
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "bookmarks.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, []);

  const handleImportFile = useCallback(
    async (file: File) => {
      try {
        const text = await file.text();
        const parsed = parseBookmarksJson(text);
        const { imported, total } = importBookmarks(parsed, { replace: replaceImport });
        setImportMessage(`Imported ${imported} bookmark${imported === 1 ? "" : "s"} (${total} total).`);
        window.dispatchEvent(new Event("rr:bookmarks"));
        setBookmarkedIds(getBookmarkedIds());
      } catch (e) {
        setImportMessage(e instanceof Error ? e.message : "Import failed");
      }
    },
    [replaceImport]
  );

  const handleClearHistory = useCallback(() => {
    clearHistory();
    setHistoryIds([]);
    setHistoryDetails({});
    setHistoryResolved(true);
  }, []);

  const hasFilters = Boolean(debouncedQ || year || topic || author);
  const items = result?.items ?? [];
  const total = result?.total ?? 0;
  const totalPages = result ? Math.max(1, Math.ceil(result.total / PAGE_SIZE)) : 1;

  const countLabel = result
    ? showSaved
      ? hasFilters
        ? `${total.toLocaleString()} saved match${total === 1 ? "" : "es"}`
        : `${total.toLocaleString()} saved paper${total === 1 ? "" : "s"}`
      : `${total.toLocaleString()} paper${total === 1 ? "" : "s"} found`
    : loading
      ? "Searching…"
      : "";

  const showHistory =
    historyIds.length > 0 && !q && !year && !topic && !author && !ranked && !hybrid && !showSaved;

  const clearAll = () => {
    applyState({ q: "", year: "", topic: "", author: "", page: 1, ranked: false, hybrid: false });
    setShowSaved(false);
  };

  const ghostBtn =
    "border border-line px-2.5 py-1.5 text-sm leading-[1.55] text-ice transition-colors hover:border-linebright";

  return (
    <div>
      {/* Console */}
      <section aria-label="Search console" className="chamfer border border-line bg-panel/70">
        <div className="grid gap-4 p-4 md:p-5">
          <div>
            <label htmlFor="rr-q" className={labelCls}>
              Search
            </label>
            <input
              id="rr-q"
              type="search"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
              placeholder="Title or abstract… (e.g. attention, large language)"
              className={`w-full ${fieldCls}`}
            />
          </div>

          <div className="flex flex-wrap items-end gap-x-5 gap-y-3">
            <div>
              <span className={labelCls} id="rr-mode-label">
                Mode
              </span>
              <div
                role="group"
                aria-labelledby="rr-mode-label"
                className="mt-1.5 flex flex-wrap border border-line"
              >
                {MODES.map((m) => {
                  const active =
                    (m.key === "ranked" && ranked) ||
                    (m.key === "hybrid" && hybrid) ||
                    (m.key === "standard" && !ranked && !hybrid);
                  return (
                    <button
                      key={m.key}
                      type="button"
                      aria-pressed={active}
                      onClick={() => {
                        setRanked(m.key === "ranked");
                        setHybrid(m.key === "hybrid");
                        setPage(1);
                      }}
                      className={`min-h-[38px] px-3 text-sm leading-[1.55] transition-colors ${
                        active
                          ? "bg-signal font-semibold text-deep"
                          : "text-ice hover:bg-well"
                      }`}
                    >
                      {m.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <Select
              id="rr-year"
              label="Year"
              value={year}
              options={[
                { value: "", label: "Any" },
                ...YEARS.map((y) => ({ value: String(y), label: String(y) })),
              ]}
              onChange={(v) => {
                setYear(v);
                setPage(1);
              }}
              className="w-24"
              mono
            />

            <Select
              id="rr-topic"
              label="Topic"
              value={topic}
              options={[
                { value: "", label: "All topics" },
                ...TOPIC_SLUGS.map((t) => ({ value: t.slug, label: t.name })),
              ]}
              onChange={(v) => {
                setTopic(v);
                setPage(1);
              }}
              className="w-52"
            />

            <div>
              <label htmlFor="rr-author" className={labelCls}>
                Author
              </label>
              <input
                id="rr-author"
                type="text"
                value={author}
                onChange={(e) => {
                  setAuthor(e.target.value);
                  setPage(1);
                }}
                placeholder="Name…"
                className={`w-44 ${fieldCls}`}
              />
            </div>

            <button
              type="button"
              aria-pressed={showSaved}
              onClick={() => {
                setShowSaved(!showSaved);
                setPage(1);
              }}
              className={`mt-1.5 inline-flex min-h-[38px] items-center gap-1.5 border px-3 text-sm leading-[1.55] transition-colors ${
                showSaved
                  ? "border-signal bg-signal font-semibold text-deep"
                  : "border-line text-ice hover:border-signal hover:text-signal"
              }`}
            >
              <span aria-hidden="true">★</span>
              <span className="tabular-nums">Saved ({bookmarkedIds.size})</span>
            </button>

            {(q || year || topic || author || ranked || hybrid || showSaved) && (
              <button
                type="button"
                onClick={clearAll}
                className="mt-1.5 min-h-[38px] px-2 text-sm leading-[1.55] text-haze transition-colors hover:text-signal"
              >
                Clear filters
              </button>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-line/50 pt-3">
            <button type="button" onClick={handleExport} className={ghostBtn}>
              Export saved
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void handleImportFile(f);
                e.target.value = "";
              }}
              aria-label="Import saved papers JSON"
            />
            <button type="button" onClick={() => fileRef.current?.click()} className={ghostBtn}>
              Import saved
            </button>
            <label className="flex cursor-pointer items-center gap-2 text-[13px] leading-[1.55] text-haze">
              <input
                type="checkbox"
                checked={replaceImport}
                onChange={(e) => setReplaceImport(e.target.checked)}
                className="h-4 w-4 accent-[#FFB03C]"
              />
              <span>Replace on import</span>
            </label>
            {importMessage && (
              <span className="font-mono text-xs leading-[1.55] text-haze">{importMessage}</span>
            )}
          </div>
        </div>
      </section>

      {error && (
        <div role="alert" className="mt-6 border border-signal/70 bg-well px-4 py-3">
          <p className="text-sm leading-[1.55] text-ice">
            Search failed. Check your connection and try again.
          </p>
          <p className="mt-1 font-mono text-xs leading-[1.55] text-haze">{error}</p>
        </div>
      )}

      {showHistory && (
        <div className="mt-6 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[11px] tracking-[0.18em] text-haze">
            Recently viewed
          </span>
          {historyIds.slice(0, 10).map((hid) => {
            const meta = historyDetails[hid];
            if (!meta && historyResolved) return null;
            return (
              <a
                key={hid}
                href={`/papers/${hid}`}
                title={meta?.title ?? `#${hid}`}
                className="max-w-xs truncate border border-line px-2.5 py-1 text-[12px] leading-[1.55] text-haze transition-colors hover:border-signal hover:text-signal"
              >
                {meta ? `${meta.title} (${meta.year})` : `#${hid}`}
              </a>
            );
          })}
          <button
            type="button"
            onClick={handleClearHistory}
            className="px-1.5 py-1 text-[12px] leading-[1.55] text-haze underline-offset-4 hover:text-signal hover:underline"
          >
            Clear history
          </button>
        </div>
      )}

      {/* Detection log */}
      <section aria-label="Results" className="mt-8">
        <p aria-live="polite" className="font-mono text-xs tabular-nums tracking-[0.14em] text-haze">
          {countLabel}
        </p>

        <div className="mt-3 border-y border-line">
          <div
            aria-hidden="true"
            className="hidden items-center gap-3 border-b border-line/60 px-4 pb-1.5 pt-2 font-mono text-[11px] tracking-[0.18em] text-haze/70 md:flex"
          >
            <span className="w-7 shrink-0">#</span>
            <span className="flex-1">Paper</span>
            <span className="w-20 shrink-0 text-right">Cited</span>
            <span className="w-12 shrink-0 text-right">Year</span>
            <span className="w-11 shrink-0" />
          </div>

          <ol>
            {items.map((paper, idx) => (
              <DetectionRow key={paper.id} paper={paper} rank={(page - 1) * PAGE_SIZE + idx + 1} />
            ))}
          </ol>

          {loading && items.length === 0 && (
            <div className="grid gap-3 px-4 py-6">
              {Array.from({ length: 6 }, (_, i) => (
                <div key={i} className="shimmer h-6 w-full" />
              ))}
            </div>
          )}

          {result && items.length === 0 && !loading && (
            <div className="px-4 py-12 text-center">
              {showSaved ? (
                hasFilters ? (
                  <>
                    <p className="text-sm leading-[1.55] text-haze">
                      No saved papers match these filters.
                    </p>
                    <p className="mt-1 font-mono text-xs tabular-nums text-haze/80">
                      Clear search to see all {bookmarkedIds.size} saved.
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        applyState({ q: "", year: "", topic: "", author: "", page: 1, ranked: false, hybrid: false });
                      }}
                      className="mt-4 border border-linebright px-3 py-1.5 text-sm text-ice transition-colors hover:border-signal hover:text-signal"
                    >
                      Clear search
                    </button>
                  </>
                ) : (
                  <>
                    <p className="text-sm leading-[1.55] text-haze">No saved papers yet.</p>
                    <p className="mt-1 text-xs leading-[1.55] text-haze/80">
                      Star a paper to pin it here.
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        setShowSaved(false);
                        setPage(1);
                      }}
                      className="mt-4 border border-linebright px-3 py-1.5 text-sm text-ice transition-colors hover:border-signal hover:text-signal"
                    >
                      Browse papers
                    </button>
                  </>
                )
              ) : (
                <>
                  <p className="text-sm leading-[1.55] text-haze">
                    No papers match these filters.
                  </p>
                  <p className="mt-1 text-xs leading-[1.55] text-haze/80">
                    Clear filters to browse all papers.
                  </p>
                  <button
                    type="button"
                    onClick={clearAll}
                    className="mt-4 border border-linebright px-3 py-1.5 text-sm text-ice transition-colors hover:border-signal hover:text-signal"
                  >
                    Clear filters
                  </button>
                </>
              )}
            </div>
          )}
        </div>

        {result && (
          <div className="mt-6">
            <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
          </div>
        )}
      </section>
    </div>
  );
}
