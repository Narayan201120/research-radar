import type { PaperListItem } from "@/lib/types";
import BookmarkButton from "@/components/BookmarkButton";

export default function PaperCard({ paper }: { paper: PaperListItem }) {
  return (
    <a
      href={`/papers/${paper.id}`}
      className="block min-w-0 rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition hover:border-indigo-300 hover:shadow"
    >
      <div className="flex items-start justify-between gap-4">
        <h3 className="text-base font-semibold text-slate-900 line-clamp-2">
          {paper.title}
        </h3>
        <div className="flex shrink-0 items-center gap-2">
          <BookmarkButton paperId={paper.id} />
          <span className="rounded bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
            {paper.publication_year}
          </span>
        </div>
      </div>
      <p className="mt-2 truncate text-sm text-slate-500">
        {paper.authors.map((a) => a.name).join(", ") || "Unknown authors"}
      </p>
      <p className="mt-1 text-sm text-slate-400">
        {paper.cited_by_count.toLocaleString()} citations
      </p>
    </a>
  );
}