import { notFound } from "next/navigation";

import CornerTicks from "@/components/CornerTicks";
import HistoryPusher from "@/components/HistoryPusher";
import SaveButton from "@/components/SaveButton";
import SiteHeader from "@/components/SiteHeader";
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
  const designation = String(paper.id).padStart(4, "0");

  return (
    <main className="min-h-screen">
      <HistoryPusher paperId={Number(id)} />
      <div className="relative mx-auto max-w-4xl px-4 pb-16 pt-8 md:px-6">
        <CornerTicks />
        <SiteHeader />

        <a
          href="/"
          className="mt-8 inline-block font-mono text-[13px] text-haze underline-offset-4 transition-colors hover:text-signal hover:underline"
        >
          &larr; Back to search
        </a>

        {/* Target file */}
        <section className="chamfer mt-4 border border-line bg-panel/70 p-5 md:p-6">
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
            <p className="font-mono text-[11px] tracking-[0.18em] text-haze">
              TARGET / {designation}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {paper.topics.map((t) => (
                <span
                  key={t.slug}
                  className="border border-line px-2 py-0.5 font-mono text-[11px] text-haze"
                >
                  {t.name}
                </span>
              ))}
            </div>
          </div>

          <h1 className="mt-3 text-[28px] font-bold leading-tight text-ice md:text-[32px]">
            {paper.title}
          </h1>

          <p className="mt-3 text-[15px] leading-[1.55] text-ice/90">{authorNames}</p>

          {/* Coordinates strip */}
          <div className="mt-5 flex flex-wrap items-center gap-x-8 gap-y-3 border-t border-line/60 pt-4">
            <div>
              <p className="font-mono text-[11px] tracking-[0.18em] text-haze/80">Year</p>
              <p className="mt-0.5 font-mono text-[15px] tabular-nums text-ice">
                {paper.publication_year}
              </p>
            </div>
            <div>
              <p className="font-mono text-[11px] tracking-[0.18em] text-haze/80">Cited by</p>
              <p className="mt-0.5 font-mono text-[15px] tabular-nums text-ice">
                {paper.cited_by_count.toLocaleString()}
              </p>
            </div>
            {paper.doi && (
              <div>
                <p className="font-mono text-[11px] tracking-[0.18em] text-haze/80">DOI</p>
                <a
                  href={paper.doi}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-0.5 block max-w-[280px] truncate font-mono text-[13px] text-signal underline-offset-4 hover:text-signaldeep hover:underline"
                >
                  {paper.doi.replace("https://doi.org/", "")}
                </a>
              </div>
            )}
            <div className="ml-auto">
              <p className="font-mono text-[11px] tracking-[0.18em] text-haze/80">Saved</p>
              <SaveButton paperId={paper.id} />
            </div>
          </div>
        </section>

        <section className="mt-8">
          <h2 className="font-mono text-[13px] tracking-[0.18em] text-haze">Abstract</h2>
          {paper.abstract ? (
            <p className="mt-3 max-w-[64ch] text-[17px] leading-[1.75] text-ice/90">
              {paper.abstract}
            </p>
          ) : (
            <p className="mt-3 max-w-[64ch] text-sm leading-[1.55] text-haze">
              No abstract for this record. Open the publisher page to read further.
            </p>
          )}
        </section>

        <section className="mt-10">
          <h2 className="font-mono text-[13px] tracking-[0.18em] text-haze">
            Similar papers
          </h2>
          {similar.length === 0 ? (
            <p className="mt-2 text-sm leading-[1.55] text-haze">
              No similar papers for this record. Open another paper to keep scanning.
            </p>
          ) : (
            <ol className="mt-3 border-y border-line">
              {similar.map((item, idx) => (
                <li
                  key={item.id}
                  className="flex items-start gap-3 border-b border-line/40 px-2 py-3 transition-colors last:border-b-0 hover:bg-panel/50 md:px-3"
                >
                  <span
                    aria-hidden="true"
                    className="w-7 shrink-0 pt-1 font-mono text-[13px] tabular-nums text-haze/80"
                  >
                    {String(idx + 1).padStart(2, "0")}
                  </span>
                  <div className="min-w-0 flex-1">
                    <a
                      href={`/papers/${item.id}`}
                      title={item.title}
                      className="block text-[16px] font-semibold leading-snug text-ice underline-offset-4 hover:text-signal hover:underline"
                    >
                      <span className="line-clamp-2 break-words">{item.title}</span>
                    </a>
                  </div>
                  <div className="flex shrink-0 items-center gap-2.5 pt-1.5">
                    <span
                      className="hidden h-1.5 w-16 border border-line sm:block"
                      role="img"
                      aria-label={`Similarity ${Math.round(item.similarity_score * 100)} percent`}
                    >
                      <span
                        className="block h-full bg-signal"
                        style={{ width: `${Math.round(item.similarity_score * 100)}%` }}
                      />
                    </span>
                    <span className="w-12 text-right font-mono text-[12px] tabular-nums text-haze">
                      {item.similarity_score.toFixed(2)}
                    </span>
                    <SaveButton paperId={item.id} />
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
