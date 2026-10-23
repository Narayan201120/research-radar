"use client";

import { useEffect, useState } from "react";

import { isBookmarked, toggleBookmark } from "@/lib/bookmarks";

export default function BookmarkButton({ paperId }: { paperId: number }) {
  const [bookmarked, setBookmarked] = useState(false);

  useEffect(() => {
    const refresh = () => setBookmarked(isBookmarked(paperId));
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
      aria-pressed={bookmarked}
      aria-label={bookmarked ? "Remove bookmark" : "Bookmark paper"}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        const now = toggleBookmark(paperId);
        setBookmarked(now);
        if (typeof window !== "undefined") window.dispatchEvent(new Event("rr:bookmarks"));
      }}
      className={`flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center rounded-full p-3 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 focus-visible:ring-offset-paper ${
        bookmarked
          ? "text-signal hover:bg-paper-deep hover:text-signal-dark"
          : "text-sage hover:bg-paper-deep hover:text-signal"
      }`}
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        className="h-5 w-5"
        fill={bookmarked ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinejoin="round"
      >
        <path d="M12 3.5l2.72 5.86 6.28.62-4.7 4.28 1.28 6.24L12 17.4l-5.58 3.1 1.28-6.24-4.7-4.28 6.28-.62L12 3.5z" />
      </svg>
    </button>
  );
}
