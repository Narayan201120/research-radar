"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import PaperCard from "@/components/PaperCard";
import Pagination from "@/components/Pagination";
import { fetchPaper, fetchPapers, TOPIC_SLUGS, YEARS } from "@/lib/api";
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

interface SearchExplorerProps {
  initialQ: string;
  initialYear: string;
  initialTopic: string;
  initialAuthor: string;
  initialPage: number;
  initialRanked?: boolean;
  initialHybrid?: boolean;
  initialSaved?: boolean;
}

export default function SearchExplorer({
  initialQ,
  initialYear,
  initialTopic,
  initialAuthor,
  initialPage,
  initialRanked = false,
  initialHybrid = false,
  initialSaved = false,
}: SearchExplorerProps) {
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

  const compact = { q: debouncedQ, year, topic, author, page, ranked, hybrid, showSaved };

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
    Promise.allSettled(ids.map((id) => fetchPaper(String(id)))).then((outcomes) => {
      if (cancelled) return;
      const next: Record<number, { title: string; year: number }> = {};
      outcomes.forEach((r, i) => {
        if (r.status === "fulfilled") {
          next[ids[i]] = { title: r.value.title, year: r.value.publication_year };
        }
        // rejected (404/network): skip
      });
      setHistoryDetails(next);
      setHistoryResolved(true);
    });
    return () => {
      cancelled = true;
    };
  }, [historyIds]);

  // Option A: intersect-then-rank on the server via ids filter.
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

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 text-left">
      <header>
        <div className="flex items-center gap-3">
          <img
            src="/logo-mark.svg"
            alt="Research Radar mark"
            width={32}
            height={32}
            className="h-8 w-8"
          />
          <h1 className="font-display text-[34px] leading-none text-ink">
            Research Radar
          </h1>
        </div>
        <p className="mt-2 text-sm leading-[1.55] text-sage">
          Search recent papers in computer vision and large language models.
        </p>
        <div aria-hidden="true" className="relative mt-4 border-t border-rule">
          <span className="absolute left-0 top-[-1px] block h-px w-24 bg-signal" />
        </div>
      </header>

      <div className="mt-6 grid gap-4">
        <input
          type="search"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          placeholder="Search title or abstract… (e.g. attention, large language)"
          className="w-full rounded-md border border-rule bg-paper px-3 py-2 text-sm leading-[1.55] text-ink placeholder:text-sage"
          aria-label="Search papers"
        />
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="flex items-center gap-2 text-sm text-sage">
            <span>Year:</span>
            <select
              value={year}
              onChange={(e) => {
                setYear(e.target.value);
                setPage(1);
              }}
              className="tnum rounded-md border border-rule bg-paper px-2 py-1.5 text-sm leading-[1.55] text-ink"
            >
              <option value="">Any</option>
              {YEARS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>
          <select
            value={topic}
            onChange={(e) => {
              setTopic(e.target.value);
              setPage(1);
            }}
            className="rounded-md border border-rule bg-paper px-2 py-1.5 text-sm leading-[1.55] text-ink"
            aria-label="Filter by topic"
          >
            <option value="">All topics</option>
            {TOPIC_SLUGS.map((t) => (
              <option key={t.slug} value={t.slug}>
                {t.name}
              </option>
            ))}
          </select>
          <input
            type="text"
            value={author}
            onChange={(e) => {
              setAuthor(e.target.value);
              setPage(1);
            }}
            placeholder="Author name…"
            className="w-44 rounded-md border border-rule bg-paper px-2 py-1.5 text-sm leading-[1.55] text-ink placeholder:text-sage"
            aria-label="Filter by author"
          />
          <label className="flex cursor-pointer items-center gap-2 text-sm leading-[1.55] text-ink">
            <input
              type="checkbox"
              checked={ranked}
              onChange={(e) => {
                const v = e.target.checked;
                setRanked(v);
                if (v) setHybrid(false);
                setPage(1);
              }}
              className="h-4 w-4 accent-signal"
            />
            <span>Ranked (BM25)</span>
          </label>
          <label className="flex cursor-pointer items-center gap-2 text-sm leading-[1.55] text-ink">
            <input
              type="checkbox"
              checked={hybrid}
              onChange={(e) => {
                const v = e.target.checked;
                setHybrid(v);
                if (v) setRanked(false);
                setPage(1);
              }}
              className="h-4 w-4 accent-signal"
            />
            <span>Hybrid (RRF)</span>
          </label>
          <label className="inline-flex cursor-pointer items-center">
            <input
              type="checkbox"
              checked={showSaved}
              onChange={(e) => {
                setShowSaved(e.target.checked);
                setPage(1);
              }}
              className="peer sr-only"
            />
            <span
              className={`tnum inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm leading-[1.55] peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-signal ${
                showSaved
                  ? "border-signal bg-signal text-white hover:bg-signal-dark"
                  : "border-rule text-ink hover:bg-paper-deep"
              }`}
            >
              <span aria-hidden="true" className={showSaved ? "text-white" : "text-signal"}>
                ★
              </span>
              <span>
                Saved ({bookmarkedIds.size})
              </span>
            </span>
          </label>
          {(year || topic || author || q || ranked || hybrid || showSaved) && (
            <button
              type="button"
              onClick={() => {
                applyState({ q: "", year: "", topic: "", author: "", page: 1, ranked: false, hybrid: false });
                setShowSaved(false);
              }}
              className="rounded-md px-2 py-1.5 text-sm leading-[1.55] text-signal hover:text-signal-dark"
            >
              Clear filters
            </button>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <button
            type="button"
            onClick={handleExport}
            className="rounded-md border border-rule px-2 py-1.5 text-sm leading-[1.55] text-ink hover:bg-paper-deep"
          >
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
            aria-label="Import bookmarks JSON"
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="rounded-md border border-rule px-2 py-1.5 text-sm leading-[1.55] text-ink hover:bg-paper-deep"
          >
            Import saved
          </button>
          <label className="flex cursor-pointer items-center gap-2 text-sm leading-[1.55] text-sage">
            <input
              type="checkbox"
              checked={replaceImport}
              onChange={(e) => setReplaceImport(e.target.checked)}
              className="h-4 w-4 accent-signal"
            />
            <span>Replace on import</span>
          </label>
          {importMessage && <span className="text-xs leading-[1.55] text-sage">{importMessage}</span>}
        </div>
      </div>

      {error && (
        <div role="alert" className="mt-6 bg-ink px-4 py-3">
          <p className="text-sm leading-[1.55] text-paper">
            Search failed. Check your connection and try again.
          </p>
          <p className="mt-1 text-xs leading-[1.55] text-paper">{error}</p>
        </div>
      )}

      {showHistory && (
        <div className="mt-6 border-t border-rule pt-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs leading-[1.55] text-sage">Recently viewed</p>
            <button
              type="button"
              onClick={handleClearHistory}
              className="rounded-md px-2 py-1 text-xs leading-[1.55] text-sage hover:text-ink"
            >
              Clear history
            </button>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {historyIds.slice(0, 10).map((hid) => {
              const meta = historyDetails[hid];
              if (!meta && historyResolved) return null;
              return (
                <a
                  key={hid}
                  href={`/papers/${hid}`}
                  title={meta?.title ?? `#${hid}`}
                  className="tnum max-w-xs truncate rounded-full border border-rule px-2.5 py-1 text-xs leading-[1.55] text-sage hover:bg-paper-deep hover:text-ink"
                >
                  {meta ? `${meta.title} (${meta.year})` : `#${hid}`}
                </a>
              );
            })}
          </div>
        </div>
      )}

      <div className="mt-6">
        <p className="tnum text-xs leading-[1.55] text-sage" aria-live="polite">
          {countLabel}
        </p>
        <div className="mt-3 divide-y divide-rule border-b border-t border-rule">
          {items.map((paper, idx) => (
            <PaperCard key={paper.id} paper={paper} rank={(page - 1) * PAGE_SIZE + idx + 1} />
          ))}
          {result && items.length === 0 && (
            <>
              {showSaved ? (
                hasFilters ? (
                  <div className="px-4 py-10 text-center">
                    <p className="text-sm leading-[1.55] text-sage">
                      No saved papers match these filters.
                    </p>
                    <p className="tnum mt-1 text-xs leading-[1.55] text-sage">
                      Clear search to see all {bookmarkedIds.size} saved.
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        applyState({ q: "", year: "", topic: "", author: "", page: 1, ranked: false, hybrid: false });
                      }}
                      className="mt-3 rounded-md border border-rule px-3 py-1.5 text-sm leading-[1.55] text-ink hover:bg-paper-deep"
                    >
                      Clear search
                    </button>
                  </div>
                ) : (
                  <div className="px-4 py-10 text-center">
                    <p className="text-sm leading-[1.55] text-sage">No saved papers yet.</p>
                    <p className="mt-1 text-xs leading-[1.55] text-sage">
                      Save papers with the star to build a list.
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        setShowSaved(false);
                        setPage(1);
                      }}
                      className="mt-3 rounded-md border border-rule px-3 py-1.5 text-sm leading-[1.55] text-ink hover:bg-paper-deep"
                    >
                      Browse papers
                    </button>
                  </div>
                )
              ) : (
                <div className="px-4 py-10 text-center">
                  <p className="text-sm leading-[1.55] text-sage">
                    No papers match these filters.
                  </p>
                  <p className="mt-1 text-xs leading-[1.55] text-sage">
                    Clear filters to browse all papers.
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      applyState({ q: "", year: "", topic: "", author: "", page: 1, ranked: false, hybrid: false });
                      setShowSaved(false);
                    }}
                    className="mt-3 rounded-md border border-rule px-3 py-1.5 text-sm leading-[1.55] text-ink hover:bg-paper-deep"
                  >
                    Clear filters
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {result && (
        <div className="mt-8">
          <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
        </div>
      )}
    </div>
  );
}
