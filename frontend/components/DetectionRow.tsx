import SaveButton from "@/components/SaveButton";
import type { PaperListItem } from "@/lib/types";

interface DetectionRowProps {
  paper: PaperListItem;
  rank: number;
}

// One numbered row of the detection log. Rank, citations, and year are
// measurement readouts (mono); the title is the contact itself.
export default function DetectionRow({ paper, rank }: DetectionRowProps) {
  const authors =
    paper.authors.map((a) => a.name).join(", ") || "Unknown authors";

  return (
    <li className="border-b border-line/40 transition-colors last:border-b-0 hover:bg-panel/50">
      <div className="flex items-start gap-3 px-3 py-3 md:px-4">
        <span
          aria-hidden="true"
          className="w-7 shrink-0 pt-1 font-mono text-[13px] tabular-nums text-haze/80"
        >
          {String(rank).padStart(2, "0")}
        </span>
        <div className="min-w-0 flex-1">
          <a
            href={`/papers/${paper.id}`}
            title={paper.title}
            className="block text-[16px] font-semibold leading-snug text-ice underline-offset-4 hover:text-signal hover:underline"
          >
            <span className="line-clamp-2 break-words">{paper.title}</span>
          </a>
          <p className="mt-1 truncate text-[13px] leading-[1.55] text-haze" title={authors}>
            {authors}
          </p>
          <p className="mt-1 font-mono text-[12px] tabular-nums text-haze/80 md:hidden">
            {paper.publication_year} / {paper.cited_by_count.toLocaleString()} citations
          </p>
        </div>
        <span
          title="Citations"
          className="hidden w-20 shrink-0 pt-1 text-right font-mono text-[13px] tabular-nums text-haze sm:block"
        >
          {paper.cited_by_count.toLocaleString()}
        </span>
        <span className="hidden w-12 shrink-0 pt-1 text-right font-mono text-[13px] tabular-nums text-haze md:block">
          {paper.publication_year}
        </span>
        <SaveButton paperId={paper.id} />
      </div>
    </li>
  );
}
