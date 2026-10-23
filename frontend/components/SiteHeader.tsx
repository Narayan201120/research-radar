import Link from "next/link";

// Shared instrument header: scope glyph, wordmark, one-line job statement.
export default function SiteHeader() {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
      <div>
        <Link
          href="/"
          className="inline-flex items-center gap-3 text-ice no-underline hover:text-ice"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.svg" alt="" width={36} height={36} className="h-9 w-9" />
          <span className="text-[30px] font-bold leading-none tracking-tight">
            Research Radar
          </span>
        </Link>
        <p className="mt-2 text-sm leading-[1.55] text-haze">
          Search recent papers in computer vision and large language models.
        </p>
      </div>
      <p className="font-mono text-[11px] leading-none tracking-[0.18em] text-haze">
        SOURCE / OPENALEX
      </p>
    </header>
  );
}
