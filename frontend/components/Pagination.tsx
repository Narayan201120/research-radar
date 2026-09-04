interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export default function Pagination({ page, totalPages, onPageChange }: PaginationProps) {
  if (totalPages <= 1) return null;

  const numbers: number[] = [];
  for (let n = Math.max(1, page - 2); n <= Math.min(totalPages, page + 2); n++) {
    numbers.push(n);
  }

  return (
    <nav className="flex items-center justify-start gap-1" aria-label="Pagination">
      <button
        type="button"
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        aria-label="Go to previous page"
        className="rounded-md border border-rule px-3 py-1.5 text-sm text-ink hover:bg-paper-deep disabled:cursor-not-allowed disabled:opacity-40"
      >
        Prev
      </button>
      {numbers[0] > 1 && (
        <>
          <button
            type="button"
            onClick={() => onPageChange(1)}
            aria-label="Go to page 1"
            className="tnum rounded-md border border-rule px-3 py-1.5 text-sm text-ink hover:bg-paper-deep"
          >
            1
          </button>
          <span aria-hidden="true" className="px-1 text-sage">
            …
          </span>
        </>
      )}
      {numbers.map((n) => (
        <button
          key={n}
          type="button"
          onClick={() => onPageChange(n)}
          aria-label={`Go to page ${n}`}
          aria-current={n === page ? "page" : undefined}
          className={`tnum rounded-md border px-3 py-1.5 text-sm ${
            n === page
              ? "border-signal bg-signal text-white hover:bg-signal-dark"
              : "border-rule text-ink hover:bg-paper-deep"
          }`}
        >
          {n}
        </button>
      ))}
      {numbers.at(-1)! < totalPages && (
        <>
          <span aria-hidden="true" className="px-1 text-sage">
            …
          </span>
          <button
            type="button"
            onClick={() => onPageChange(totalPages)}
            aria-label={`Go to page ${totalPages}`}
            className="tnum rounded-md border border-rule px-3 py-1.5 text-sm text-ink hover:bg-paper-deep"
          >
            {totalPages}
          </button>
        </>
      )}
      <button
        type="button"
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        aria-label="Go to next page"
        className="rounded-md border border-rule px-3 py-1.5 text-sm text-ink hover:bg-paper-deep disabled:cursor-not-allowed disabled:opacity-40"
      >
        Next
      </button>
    </nav>
  );
}