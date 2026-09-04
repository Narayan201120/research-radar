import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-paper px-4 font-sans text-ink">
      <div className="max-w-md text-center">
        <h1 className="font-display text-[34px] leading-tight text-ink">
          No paper at this address
        </h1>
        <p className="mt-3 text-sm leading-[1.55] text-sage">
          The paper was not found. Check the address or return to search to
          keep looking.
        </p>
        <Link
          href="/"
          className="mt-6 inline-block rounded-full bg-signal px-4 py-2 text-sm font-medium text-white hover:bg-signal-dark"
        >
          Back to search
        </Link>
      </div>
    </main>
  );
}
