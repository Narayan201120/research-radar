"use client";

import { useEffect, useState } from "react";

import { isBookmarked, toggleBookmark } from "@/lib/bookmarks";

export default function SaveButton({ paperId }: { paperId: number }) {
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const refresh = () => setSaved(isBookmarked(paperId));
    refresh();
    window.addEventListener("rr:bookmarks", refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener("rr:bookmarks", refresh);
      window.removeEventListener("storage", refresh);
    };
  }, [paperId]);

  return (
    <button
      type="button"
      aria-pressed={saved}
      aria-label={saved ? "Remove saved paper" : "Save paper"}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        const now = toggleBookmark(paperId);
        setSaved(now);
        if (typeof window !== "undefined") window.dispatchEvent(new Event("rr:bookmarks"));
      }}
      className={`flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center border border-transparent p-2.5 transition-colors ${
        saved
          ? "text-signal hover:text-signaldeep"
          : "text-haze hover:border-line hover:text-signal"
      }`}
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        className="h-5 w-5"
        fill={saved ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinejoin="round"
      >
        <path d="M12 3.5l2.72 5.86 6.28.62-4.7 4.28 1.28 6.24L12 17.4l-5.58 3.1 1.28-6.24-4.7-4.28 6.28-.62L12 3.5z" />
      </svg>
    </button>
  );
}
