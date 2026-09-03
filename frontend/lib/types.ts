export interface AuthorBrief {
  id: number;
  name: string;
}

export interface TopicBrief {
  id: number;
  name: string;
  slug: string;
}

export interface PaperListItem {
  id: number;
  title: string;
  publication_year: number;
  cited_by_count: number;
  authors: AuthorBrief[];
}

export interface PaperListResponse {
  items: PaperListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface PaperDetail {
  id: number;
  title: string;
  abstract: string | null;
  publication_year: number;
  doi: string | null;
  cited_by_count: number;
  created_at: string;
  authors: AuthorBrief[];
  topics: TopicBrief[];
}

export interface SimilarItem {
  id: number;
  title: string;
  similarity_score: number;
}

export interface PaperQuery {
  q?: string;
  year?: string;
  topic?: string;
  author?: string;
  ids?: string;
  page?: number;
  page_size?: number;
  ranked?: boolean;
  hybrid?: boolean;
}