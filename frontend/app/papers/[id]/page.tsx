import { notFound } from "next/navigation";

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

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-4xl px-4 py-10">
        <a
          href="/"
          className="text-sm font-medium text-indigo-600 hover:text-indigo-800"
        >
          ← Back to search
        </a>

        <div className="mt-4 flex items-start justify-between gap-6">
          <h1 className="text-2xl font-bold text-slate-900 sm:text-3xl">
            {paper.title}
          </h1>
          <span className="shrink-0 rounded bg-indigo-50 px-2 py-1 text-sm font-medium text-indigo-700">
            {paper.publication_year}
          </span>
        </div>

        <p className="mt-3 text-sm text-slate-500">
          {paper.authors.map((a) => a.name).join(", ") || "Unknown authors"}
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
          <span className="rounded-full bg-white px-3 py-1 border border-slate-200 text-slate-600">
            {paper.cited_by_count.toLocaleString()} citations
          </span>
          {paper.topics.map((t) => (
            <span
              key={t.slug}
              className="rounded-full bg-emerald-50 px-3 py-1 border border-emerald-200 text-emerald-700"
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
            className="mt-3 inline-block text-sm text-indigo-600 hover:text-indigo-800"
          >
            View publisher page ↗
          </a>
        )}

        <section className="mt-8">
          <h2 className="text-lg font-semibold text-slate-900">Abstract</h2>
          {paper.abstract ? (
            <p className="mt-2 leading-relaxed text-slate-600">{paper.abstract}</p>
          ) : (
            <p className="mt-2 text-sm italic text-slate-400">
              No abstract available from the source.
            </p>
          )}
        </section>

        <section className="mt-10">
          <h2 className="text-lg font-semibold text-slate-900">Similar papers</h2>
          {similar.length === 0 ? (
            <p className="mt-2 text-sm text-slate-400">
              No similar papers found.
            </p>
          ) : (
            <div className="mt-3 grid gap-3">
              {similar.map((item) => (
                <a
                  key={item.id}
                  href={`/papers/${item.id}`}
                  className="flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition hover:border-indigo-300 hover:shadow"
                >
                  <span className="font-medium text-slate-800 line-clamp-2">
                    {item.title}
                  </span>
                  <span className="shrink-0 rounded bg-indigo-50 px-2 py-0.5 text-xs font-semibold text-indigo-700">
                    {item.similarity_score.toFixed(2)}
                  </span>
                </a>
              ))}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}