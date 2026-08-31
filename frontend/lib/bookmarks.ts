const KEY_BOOKMARKS = "rr:bookmarks";
const KEY_HISTORY = "rr:history";
const HISTORY_MAX = 20;

function isBrowser(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function readIds(key: string): number[] {
  if (!isBrowser()) return [];
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((v): v is number => typeof v === "number");
  } catch {
    return [];
  }
}

function writeIds(key: string, ids: number[]): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(key, JSON.stringify(ids));
  } catch {}
}

export function getBookmarkedIds(): Set<number> {
  return new Set(readIds(KEY_BOOKMARKS));
}

export function isBookmarked(id: number): boolean {
  return getBookmarkedIds().has(id);
}

export function toggleBookmark(id: number): boolean {
  const ids = readIds(KEY_BOOKMARKS);
  const idx = ids.indexOf(id);
  let next: number[];
  let nowBookmarked: boolean;
  if (idx >= 0) {
    next = ids.filter((v) => v !== id);
    nowBookmarked = false;
  } else {
    next = [...ids, id];
    nowBookmarked = true;
  }
  writeIds(KEY_BOOKMARKS, next);
  return nowBookmarked;
}

export function getHistoryIds(): number[] {
  return readIds(KEY_HISTORY);
}

export function pushHistory(id: number): void {
  const ids = readIds(KEY_HISTORY);
  const filtered = ids.filter((v) => v !== id);
  filtered.unshift(id);
  writeIds(KEY_HISTORY, filtered.slice(0, HISTORY_MAX));
}
