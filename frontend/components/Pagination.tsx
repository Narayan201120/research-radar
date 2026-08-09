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
    <nav className="flex items-center justify-center gap-1" aria-label="Pagination">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Prev
      </button>
      {numbers[0] > 1 && (
        <>
          <button
            onClick={() => onPageChange(1)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          >
            1
          </button>
          <span className="px-1 text-slate-400">…</span>
        </>
      )}
      {numbers.map((n) => (
        <button
          key={n}
          onClick={() => onPageChange(n)}
          className={`rounded-md border px-3 py-1.5 text-sm ${
            n === page
              ? "border-indigo-600 bg-indigo-600 text-white"
              : "border-slate-300 text-slate-600 hover:bg-slate-50"
          }`}
        >
          {n}
        </button>
      ))}
      {numbers.at(-1)! < totalPages && (
        <>
          <span className="px-1 text-slate-400">…</span>
          <button
            onClick={() => onPageChange(totalPages)}
            className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          >
            {totalPages}
          </button>
        </>
      )}
      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Next
      </button>
    </nav>
  );
}