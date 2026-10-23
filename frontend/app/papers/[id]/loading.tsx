export default function Loading() {
  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-4xl px-4 pb-16 pt-8 md:px-6">
        <div className="shimmer h-10 w-64" />
        <div className="shimmer mt-8 h-5 w-36" />
        <div className="shimmer mt-4 h-16 w-full" />
        <div className="shimmer mt-3 h-5 w-1/2" />
        <div className="shimmer mt-6 h-24 w-full" />
        <div className="mt-10 grid gap-3">
          {Array.from({ length: 5 }, (_, i) => (
            <div key={i} className="shimmer h-14 w-full" />
          ))}
        </div>
      </div>
    </main>
  );
}
