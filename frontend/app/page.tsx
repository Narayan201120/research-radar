import SearchExplorer from "@/components/SearchExplorer";

interface HomeSearchParams {
  q?: string;
  year?: string;
  topic?: string;
  author?: string;
  page?: string;
}

export default function HomePage({ searchParams }: { searchParams: HomeSearchParams }) {
  return (
    <main className="min-h-screen bg-slate-50">
      <SearchExplorer
        initialQ={searchParams.q ?? ""}
        initialYear={searchParams.year ?? ""}
        initialTopic={searchParams.topic ?? ""}
        initialAuthor={searchParams.author ?? ""}
        initialPage={Math.max(1, Number(searchParams.page) || 1)}
      />
    </main>
  );
}