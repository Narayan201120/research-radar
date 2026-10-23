import { notFound } from "next/navigation";

import HistoryPusher from "@/components/HistoryPusher";
import BookmarkButton from "@/components/BookmarkButton";
import { fetchPaper, fetchSimilar } from "@/lib/api";

export const revalidate = 60;

export default async function PaperDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const paper = await fetchPaper(id).catch(() => null);
  if (!paper) notFound();

  const similar = await fetchSimilar(id).catch(() => []);

  const authorNames =
    paper.authors.map((a) => a.name).join(", ") || "Unknown authors";

  return (
    <main className="min-h-screen bg-paper font-sans text-ink">
      <HistoryPusher paperId={Number(id)} />
      <div className="mx-auto max-w-4xl px-4 py-10">
        <a
          href="/"
          className="text-sm font-medium text-signal hover:text-signal-dark hover:underline hover:underline-offset-4"
        >
          <span aria-hidden="true">← </span>Back to search
        </a>

        <h1
          title={paper.title}
          className="mt-6 font-display text-[30px] leading-tight text-ink"
        >
          {paper.title}
        </h1>

        <div className="mt-4 flex items-center justify-between gap-4 border-y border-rule py-2">
          <span className="tnum text-sm text-sage">
            {paper.publication_year}
          </span>
          <span className="flex min-h-[44px] min-w-[44px] items-center justify-center">
            <BookmarkButton paperId={Number(id)} />
          </span>
        </div>

        <p
          title={authorNames}
          className="mt-4 truncate text-sm leading-[1.55] text-ink"
        >
          {authorNames}
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-2 border-b border-rule pb-4">
          <span className="tnum text-sm text-sage">
            {paper.cited_by_count.toLocaleString()} citations
          </span>
          {paper.topics.map((t) => (
            <span
              key={t.slug}
              className="rounded-full border border-rule px-3 py-1 text-xs text-sage"
            >
              {t.name}
            </span>
          ))}
        </div>

        {paper.doi && (
          <a
            href={paper.doi}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-block text-sm text-signal hover:text-signal-dark hover:underline hover:underline-offset-4"
          >
            View publisher page
          </a>
        )}

        <section className="mt-8">
          <h2 className="text-[20px] font-semibold leading-[1.55] text-ink">
            Abstract
          </h2>
          {paper.abstract ? (
            <p className="mt-3 max-w-[68ch] font-display text-base leading-[1.7] text-ink">
              {paper.abstract}
            </p>
          ) : (
            <p className="mt-3 max-w-[68ch] text-sm leading-[1.55] text-sage">
              No abstract for this record. Open the publisher page to read
              further.
            </p>
          )}
        </section>

        <section className="mt-10">
          <h2 className="text-[20px] font-semibold leading-[1.55] text-ink">
            Similar papers
          </h2>
          {similar.length === 0 ? (
            <p className="mt-2 text-sm leading-[1.55] text-sage">
              No similar papers for this record. Open another paper to keep
              scanning.
            </p>
          ) : (
            <ol className="mt-3 border-t border-rule">
              {similar.map((item, idx) => (
                <li
                  key={item.id}
                  className="flex items-start gap-3 border-b border-rule px-2 py-3 hover:bg-paper-deep"
                >
                  <span
                    aria-hidden="true"
                    className="tnum w-[2ch] shrink-0 pt-1 text-xs text-signal md:text-sm"
                  >
                    {String(idx + 1).padStart(2, "0")}
                  </span>
                  <div className="min-w-0 flex-1">
                    <a
                      href={`/papers/${item.id}`}
                      title={item.title}
                      className="block min-w-0 text-[16px] font-medium leading-[1.55] text-ink hover:underline hover:underline-offset-4"
                    >
                      <span className="block line-clamp-2 break-words">
                        {item.title}
                      </span>
                    </a>
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <span className="flex min-h-[44px] min-w-[44px] items-center justify-center">
                      <BookmarkButton paperId={item.id} />
                    </span>
                    <span className="tnum shrink-0 rounded-full border border-rule px-2 py-0.5 text-xs font-medium text-ink">
                      {item.similarity_score.toFixed(2)}
                    </span>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </main>
  );
}
