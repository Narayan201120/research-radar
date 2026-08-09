"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import PaperCard from "@/components/PaperCard";
import Pagination from "@/components/Pagination";
import { fetchPapers, TOPIC_SLUGS, YEARS } from "@/lib/api";
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
}

export default function SearchExplorer({
  initialQ,
  initialYear,
  initialTopic,
  initialAuthor,
  initialPage,
}: SearchExplorerProps) {
  const router = useRouter();
  const pathname = usePathname();

  const [q, setQ] = useState(initialQ);
  const [year, setYear] = useState(initialYear);
  const [topic, setTopic] = useState(initialTopic);
  const [author, setAuthor] = useState(initialAuthor);
  const [page, setPage] = useState(initialPage);

  const [result, setResult] = useState<PaperListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const debouncedQ = useDebouncedValue(q, DEBOUNCE_MS);

  const applyState = useCallback(
    (next: { q?: string; year?: string; topic?: string; author?: string; page?: number }) => {
      setQ((v) => next.q ?? v);
      setYear((v) => next.year ?? v);
      setTopic((v) => next.topic ?? v);
      setAuthor((v) => next.author ?? v);
      setPage((v) => next.page ?? v);
    },
    []
  );

  const syncUrl = useCallback(
    (value: { q: string; year: string; topic: string; author: string; page: number }) => {
      const search = new URLSearchParams();
      if (value.q) search.set("q", value.q);
      if (value.year) search.set("year", value.year);
      if (value.topic) search.set("topic", value.topic);
      if (value.author) search.set("author", value.author);
      if (value.page > 1) search.set("page", String(value.page));
      const qs = search.toString();
      router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
    },
    [pathname, router]
  );

  const compact = { q: debouncedQ, year, topic, author, page };

  useEffect(() => {
    setLoading(true);
    setError(null);
    let cancelled = false;

    fetchPapers({ q: debouncedQ, year, topic, author, page, page_size: PAGE_SIZE })
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
  }, [debouncedQ, year, topic, author, page]);

  useEffect(() => {
    syncUrl(compact);
  }, [compact, syncUrl]);

  const totalPages = result ? Math.max(1, Math.ceil(result.total / PAGE_SIZE)) : 1;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="flex items-center gap-3">
        <img
          src="/logo-mark.svg"
          alt="Research Radar mark"
          width={130}
          height={130}
          className="h-14 w-auto"
        />
        <h1 className="text-3xl font-bold text-slate-900">Research Radar</h1>
      </div>
      <p className="mt-1 text-slate-500">
        Search recent papers in computer vision and large language models.
      </p>

      <div className="mt-6 grid gap-4">
        <input
          type="search"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          placeholder="Search title or abstract… (e.g. attention, large language)"
          className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          aria-label="Search papers"
        />
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="flex items-center gap-2">
            <span className="text-slate-500">Year:</span>
            <select
              value={year}
              onChange={(e) => {
                setYear(e.target.value);
                setPage(1);
              }}
              className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-slate-700"
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
            className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-slate-700"
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
            className="w-44 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-slate-700 placeholder:text-slate-400"
            aria-label="Filter by author"
          />
          {(year || topic || author || q) && (
            <button
              onClick={() => applyState({ q: "", year: "", topic: "", author: "", page: 1 })}
              className="rounded-md px-2 py-1.5 text-indigo-600 hover:text-indigo-800"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {error && (
        <p className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="mt-6">
        <p className="text-sm text-slate-400" aria-live="polite">
          {result
            ? `${result.total.toLocaleString()} paper${result.total === 1 ? "" : "s"} found`
            : loading
              ? "Searching…"
              : ""}
        </p>
        <div className="mt-3 grid gap-3">
          {result?.items.map((paper) => (
            <PaperCard key={paper.id} paper={paper} />
          ))}
          {result?.items.length === 0 && (
            <p className="rounded-lg border border-slate-200 bg-white px-4 py-8 text-center text-slate-400">
              No papers match your filters.
            </p>
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