"use client";

import { useEffect } from "react";

import { pushHistory } from "@/lib/bookmarks";

export default function HistoryPusher({ paperId }: { paperId: number }) {
  useEffect(() => {
    if (Number.isFinite(paperId)) pushHistory(paperId);
  }, [paperId]);
  return null;
}
