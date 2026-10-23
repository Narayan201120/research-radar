import { API_BASE_URL, SERVER_API_BASE_URL } from "./config";
import type {
  PaperDetail,
  PaperListResponse,
  PaperQuery,
  SimilarItem,
} from "./types";

export const TOPIC_SLUGS = [
  { slug: "computer-vision", name: "Computer Vision" },
  { slug: "large-language-models", name: "Large Language Models" },
];

export const YEARS = Array.from({ length: 10 }, (_, i) => 2026 - i);

async function getJson<T>(baseUrl: string, path: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${path}`);
  }
  return response.json() as Promise<T>;
}

// Server-side fetches prefer the docker-internal host. Outside docker
// (local dev against a localhost backend) that host is unreachable, so
// fall back to the browser-facing base URL before giving up.
async function getJsonServer<T>(path: string): Promise<T> {
  try {
    return await getJson<T>(SERVER_API_BASE_URL, path);
  } catch {
    return getJson<T>(API_BASE_URL, path);
  }
}

function buildQuery(params: PaperQuery): URLSearchParams {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "" && value !== 0) {
      if (key === "page" && (value as number) <= 1) continue;
      search.set(key, String(value));
    }
  }
  return search;
}

export function fetchPapers(query: PaperQuery): Promise<PaperListResponse> {
  const search = buildQuery(query);
  return getJson<PaperListResponse>(API_BASE_URL, `/papers?${search.toString()}`);
}

export function fetchPaper(id: string): Promise<PaperDetail> {
  return getJsonServer<PaperDetail>(`/papers/${id}`);
}

// Browser-side single-paper fetch. fetchPaper uses SERVER_API_BASE_URL,
// which is unreachable from real browsers (non-NEXT_PUBLIC env never ships
// to the client bundle), so client components must use this instead.
export function fetchPaperClient(id: string): Promise<PaperDetail> {
  return getJson<PaperDetail>(API_BASE_URL, `/papers/${id}`);
}

export function fetchSimilar(id: string): Promise<SimilarItem[]> {
  return getJsonServer<SimilarItem[]>(`/papers/${id}/similar`);
}
