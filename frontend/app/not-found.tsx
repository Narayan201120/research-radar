import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="text-center">
        <p className="font-mono text-sm tracking-[0.18em] text-signal">
          404 / NO CONTACT
        </p>
        <h1 className="mt-3 text-2xl font-bold text-ice">
          This page is not in the index.
        </h1>
        <p className="mt-2 text-sm leading-[1.55] text-haze">
          The paper may have been removed, or the address is wrong.
        </p>
        <Link
          href="/"
          className="mt-6 inline-block border border-linebright px-4 py-2 text-sm text-ice transition-colors hover:border-signal hover:text-signal"
        >
          Return to search
        </Link>
      </div>
    </main>
  );
}
