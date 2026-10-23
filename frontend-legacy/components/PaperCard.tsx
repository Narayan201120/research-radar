import type { PaperListItem } from "@/lib/types";
import BookmarkButton from "@/components/BookmarkButton";

interface PaperCardProps {
  paper: PaperListItem;
  rank?: number;
}

export default function PaperCard({ paper, rank }: PaperCardProps) {
  const authorsFull =
    paper.authors.map((a) => a.name).join(", ") || "Unknown authors";
  const showRank = typeof rank === "number";

  return (
    <div className="border-b border-rule hover:bg-paper-deep">
      <div className="flex min-w-0 items-start gap-3 py-4">
        {showRank ? (
          <span
            aria-hidden="true"
            className="tnum w-[2ch] shrink-0 pt-1 text-xs text-signal sm:text-sm"
          >
            {String(rank).padStart(2, "0")}
          </span>
        ) : null}
        <div className="min-w-0 flex-1">
          <a
            href={`/papers/${paper.id}`}
            title={paper.title}
            className="block rounded-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 focus-visible:ring-offset-paper"
          >
            <h3 className="line-clamp-2 text-base font-medium leading-snug text-ink">
              {paper.title}
            </h3>
          </a>
          <p
            title={authorsFull}
            className="mt-1 truncate text-xs text-sage"
          >
            <span>{authorsFull}</span>
            <span aria-hidden="true"> · </span>
            <span className="tnum">{paper.publication_year}</span>
            <span aria-hidden="true"> · </span>
            <span className="tnum">
              {paper.cited_by_count.toLocaleString()} citations
            </span>
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <BookmarkButton paperId={paper.id} />
          <span className="tnum hidden shrink-0 whitespace-nowrap rounded-full border border-rule px-2 py-0.5 text-xs text-sage min-[480px]:inline-flex">
            {paper.publication_year}
          </span>
        </div>
      </div>
    </div>
  );
}
