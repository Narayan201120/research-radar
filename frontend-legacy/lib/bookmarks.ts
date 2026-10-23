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

export function exportBookmarks(): number[] {
  return readIds(KEY_BOOKMARKS);
}

export function exportBookmarksJson(): string {
  return JSON.stringify(readIds(KEY_BOOKMARKS));
}

export function parseBookmarksJson(text: string): number[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text) as unknown;
  } catch {
    throw new Error("Invalid bookmarks JSON: malformed JSON");
  }
  if (!Array.isArray(parsed)) {
    throw new Error("Invalid bookmarks JSON: expected array");
  }
  return parsed.filter((v): v is number => typeof v === "number");
}

export function importBookmarks(
  data: unknown,
  opts?: { replace?: boolean }
): { imported: number; total: number } {
  const current = readIds(KEY_BOOKMARKS);
  if (!Array.isArray(data)) {
    return { imported: 0, total: current.length };
  }
  const valid = [...new Set(data.filter((v): v is number => typeof v === "number"))];
  if (opts?.replace === true) {
    writeIds(KEY_BOOKMARKS, valid);
    return { imported: valid.length, total: valid.length };
  }
  const existing = new Set(current);
  const fresh = valid.filter((id) => !existing.has(id));
  const next = [...current, ...fresh];
  writeIds(KEY_BOOKMARKS, next);
  return { imported: fresh.length, total: next.length };
}

export function clearHistory(): void {
  writeIds(KEY_HISTORY, []);
}
