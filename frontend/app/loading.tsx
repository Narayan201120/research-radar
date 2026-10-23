export default function Loading() {
  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-5xl px-4 pb-16 pt-8 md:px-6">
        <div className="shimmer h-10 w-64" />
        <div className="shimmer mt-6 h-72 w-full" />
        <div className="shimmer mt-6 h-44 w-full" />
        <div className="mt-8 grid gap-4">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="shimmer h-7 w-full" />
          ))}
        </div>
      </div>
    </main>
  );
}
