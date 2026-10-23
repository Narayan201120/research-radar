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

  const base =
    "min-h-[36px] border px-3 font-mono text-[13px] tabular-nums transition-colors disabled:cursor-not-allowed disabled:opacity-40";

  return (
    <nav className="flex flex-wrap items-center gap-1.5" aria-label="Pagination">
      <button
        type="button"
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        aria-label="Go to previous page"
        className={`${base} border-line text-ice hover:border-linebright disabled:hover:border-line`}
      >
        Prev
      </button>
      {numbers[0] > 1 && (
        <>
          <button
            type="button"
            onClick={() => onPageChange(1)}
            aria-label="Go to page 1"
            className={`${base} border-line text-ice hover:border-linebright`}
          >
            1
          </button>
          <span aria-hidden="true" className="px-0.5 font-mono text-haze">
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
          className={`${base} ${
            n === page
              ? "border-signal bg-signal text-deep"
              : "border-line text-ice hover:border-linebright"
          }`}
        >
          {n}
        </button>
      ))}
      {numbers.at(-1)! < totalPages && (
        <>
          <span aria-hidden="true" className="px-0.5 font-mono text-haze">
            …
          </span>
          <button
            type="button"
            onClick={() => onPageChange(totalPages)}
            aria-label={`Go to page ${totalPages}`}
            className={`${base} border-line text-ice hover:border-linebright`}
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
        className={`${base} border-line text-ice hover:border-linebright disabled:hover:border-line`}
      >
        Next
      </button>
    </nav>
  );
}
