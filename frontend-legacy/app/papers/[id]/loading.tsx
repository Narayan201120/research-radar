export default function Loading() {
  return (
    <main
      aria-busy="true"
      aria-label="Loading paper"
      className="min-h-screen bg-paper font-sans text-ink"
    >
      <div className="mx-auto max-w-4xl px-4 py-10">
        <span className="sr-only">Loading paper…</span>
        <div aria-hidden="true">
          <div className="skeleton h-4 w-28" />
          <div className="mt-4 flex items-start justify-between gap-6">
            <div className="min-w-0 flex-1">
              <div className="skeleton h-[30px] w-full" />
              <div className="skeleton mt-2 h-[30px] w-2/3" />
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <div className="skeleton h-8 w-8" />
              <div className="skeleton h-6 w-14 rounded-full" />
            </div>
          </div>
          <div className="skeleton mt-3 h-4 w-2/3" />
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <div className="skeleton h-6 w-28 rounded-full" />
            <div className="skeleton h-6 w-24 rounded-full" />
          </div>
          <div className="skeleton mt-3 h-4 w-40" />
          <section className="mt-8">
            <div className="skeleton h-5 w-32" />
            <div className="mt-2 max-w-[68ch]">
              <div className="skeleton h-4 w-full" />
              <div className="skeleton mt-2 h-4 w-full" />
              <div className="skeleton mt-2 h-4 w-full" />
              <div className="skeleton mt-2 h-4 w-11/12" />
              <div className="skeleton mt-2 h-4 w-1/3" />
            </div>
          </section>
          <section className="mt-10">
            <div className="skeleton h-5 w-36" />
            <div className="mt-3 border-t border-rule">
              <div className="flex items-center justify-between gap-4 border-b border-rule py-4">
                <div className="min-w-0 flex-1">
                  <div className="skeleton h-4 w-3/4" />
                  <div className="skeleton mt-2 h-3 w-1/2" />
                </div>
                <div className="skeleton h-5 w-12 shrink-0 rounded-full" />
              </div>
              <div className="flex items-center justify-between gap-4 border-b border-rule py-4">
                <div className="min-w-0 flex-1">
                  <div className="skeleton h-4 w-2/3" />
                  <div className="skeleton mt-2 h-3 w-1/3" />
                </div>
                <div className="skeleton h-5 w-12 shrink-0 rounded-full" />
              </div>
              <div className="flex items-center justify-between gap-4 border-b border-rule py-4">
                <div className="min-w-0 flex-1">
                  <div className="skeleton h-4 w-3/4" />
                  <div className="skeleton mt-2 h-3 w-2/5" />
                </div>
                <div className="skeleton h-5 w-12 shrink-0 rounded-full" />
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
