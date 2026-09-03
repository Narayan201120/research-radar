import SearchExplorer from "@/components/SearchExplorer";

interface HomeSearchParams {
  q?: string;
  year?: string;
  topic?: string;
  author?: string;
  page?: string;
  ranked?: string;
  hybrid?: string;
  saved?: string;
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<HomeSearchParams>;
}) {
  const params = await searchParams;
  return (
    <main className="min-h-screen bg-slate-50">
      <SearchExplorer
        initialQ={params.q ?? ""}
        initialYear={params.year ?? ""}
        initialTopic={params.topic ?? ""}
        initialAuthor={params.author ?? ""}
        initialPage={Math.max(1, Number(params.page) || 1)}
        initialRanked={params.ranked === "true"}
        initialHybrid={params.hybrid === "true"}
        initialSaved={params.saved === "true"}
      />
    </main>
  );
}