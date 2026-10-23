import CornerTicks from "@/components/CornerTicks";
import RadarScope from "@/components/RadarScope";
import SearchConsole from "@/components/SearchConsole";
import SiteHeader from "@/components/SiteHeader";

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
    <main className="min-h-screen">
      <div className="relative mx-auto max-w-5xl px-4 pb-16 pt-8 md:px-6">
        <CornerTicks />
        <SiteHeader />
        <section
          aria-label="Latest detections"
          className="chamfer mt-6 border border-line bg-panel/40"
        >
          <RadarScope />
        </section>
        <div className="mt-6">
          <SearchConsole
            initialQ={params.q ?? ""}
            initialYear={params.year ?? ""}
            initialTopic={params.topic ?? ""}
            initialAuthor={params.author ?? ""}
            initialPage={Math.max(1, Number(params.page) || 1)}
            initialRanked={params.ranked === "true"}
            initialHybrid={params.hybrid === "true"}
            initialSaved={params.saved === "true"}
          />
        </div>
      </div>
    </main>
  );
}
