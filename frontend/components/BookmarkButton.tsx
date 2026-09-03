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
      className={`shrink-0 rounded px-2 py-1 text-xs font-medium border transition ${
        bookmarked
          ? "bg-indigo-600 text-white border-indigo-600"
          : "bg-white text-slate-600 border-slate-200 hover:border-indigo-300"
      }`}
    >
      {bookmarked ? "★ Saved" : "☆ Save"}
    </button>
  );
}
