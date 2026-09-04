export default function Loading() {
  return (
    <main
      aria-busy="true"
      aria-label="Loading results"
      className="min-h-screen bg-paper font-sans text-ink"
    >
      <div className="mx-auto max-w-5xl px-4 py-8">
        <span className="sr-only">Loading results…</span>
        <div aria-hidden="true">
          <div className="skeleton h-[34px] w-56 max-w-full" />
          <div className="skeleton mt-3 h-4 w-80 max-w-full" />
          <div className="mt-6 h-px bg-rule" />
          <div className="skeleton mt-6 h-3 w-40 max-w-full" />
          <div className="mt-4 border-t border-rule">
            <div className="flex items-start gap-4 border-b border-rule py-4">
              <div className="skeleton h-4 w-8 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="skeleton h-4 w-3/4" />
                <div className="skeleton mt-2 h-3 w-1/2" />
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <div className="skeleton h-6 w-6" />
                <div className="skeleton h-6 w-14 rounded-full" />
              </div>
            </div>
            <div className="flex items-start gap-4 border-b border-rule py-4">
              <div className="skeleton h-4 w-8 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="skeleton h-4 w-2/3" />
                <div className="skeleton mt-2 h-3 w-1/3" />
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <div className="skeleton h-6 w-6" />
                <div className="skeleton h-6 w-14 rounded-full" />
              </div>
            </div>
            <div className="flex items-start gap-4 border-b border-rule py-4">
              <div className="skeleton h-4 w-8 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="skeleton h-4 w-3/4" />
                <div className="skeleton mt-2 h-3 w-2/5" />
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <div className="skeleton h-6 w-6" />
                <div className="skeleton h-6 w-14 rounded-full" />
              </div>
            </div>
            <div className="flex items-start gap-4 border-b border-rule py-4">
              <div className="skeleton h-4 w-8 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="skeleton h-4 w-1/2" />
                <div className="skeleton mt-2 h-3 w-1/2" />
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <div className="skeleton h-6 w-6" />
                <div className="skeleton h-6 w-14 rounded-full" />
              </div>
            </div>
            <div className="flex items-start gap-4 border-b border-rule py-4">
              <div className="skeleton h-4 w-8 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="skeleton h-4 w-2/3" />
                <div className="skeleton mt-2 h-3 w-1/3" />
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <div className="skeleton h-6 w-6" />
                <div className="skeleton h-6 w-14 rounded-full" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
