export interface User {
  id: number;
  email: string;
  display_name: string;
  is_admin: boolean;
  is_active: boolean;
  created_at: string;
  last_login: string | null;
}

export interface WordBox {
  text: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export type IssueType = "normal" | "hs" | "sp";

export interface Tag {
  id: number;
  name: string;
}

export interface Magazine {
  id: number;
  title: string;
  issue_number: string | null;
  publication_date: string | null;
  issue_month: string | null;
  issue_type: IssueType;
  filename: string;
  cover_thumbnail_path: string | null;
  scan_status: "detected" | "stable" | "queued" | "processing" | "done" | "failed";
  error_message: string | null;
  toc_status: "pending" | "processing" | "done" | "failed";
  toc_error_message: string | null;
  collection_id: number | null;
  collection_name: string | null;
  tags: Tag[];
  created_at: string;
  file_size: number;
  page_count: number;
  article_count: number;
}

export interface Article {
  id: number;
  magazine_id: number;
  title: string;
  start_page: number;
  end_page: number | null;
}

export interface ArticleWithMagazine extends Article {
  magazine_title: string;
  magazine_issue_number: string | null;
}

export interface MagazineTheme {
  id: number;
  name: string;
  magazine_count: number;
}

export interface YearFacet {
  year: number;
  count: number;
}

export interface MagazineFacets {
  years: YearFacet[];
  hs_count: number;
  sp_count: number;
}

export interface Collection {
  id: number;
  name: string;
  tags: Tag[];
}

export interface CollectionSummary extends Collection {
  magazine_count: number;
  cover_magazine_id: number | null;
}

export interface LibraryOverview {
  collections: CollectionSummary[];
  unassigned_count: number;
  unassigned_cover_magazine_id: number | null;
}

export interface GeminiModelOption {
  id: string;
  label: string;
}

export interface GeminiSettings {
  model: string;
  available_models: GeminiModelOption[];
  daily_request_limit: number | null;
  rpm_limit: number | null;
  requests_used_today: number;
}

export interface Page {
  id: number;
  magazine_id: number;
  page_number: number;
  raw_text: string | null;
  language: "fr" | "en" | "mixed" | null;
  words: WordBox[] | null;
  ocr_status: "pending" | "processing" | "done" | "failed";
  error_message: string | null;
}

export interface SearchHit {
  magazine_id: number;
  magazine_title: string;
  occurrence_count: number;
  page_number: number;
  page_id: number;
  snippet: string;
  words: WordBox[];
}

export interface SearchResponse {
  query: string;
  total_hits: number;
  hits: SearchHit[];
  processing_time_ms: number;
}

export interface ScanTriggerResponse {
  job_id: string;
  new_files_detected: number;
}

export interface ScanStatusResponse {
  job_id: string;
  detected: number;
  processing: number;
  done: number;
  failed: number;
  finished: boolean;
}

export interface RetryFailedResponse {
  retried: number;
}

export type LogLevel = "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
export type LogComponent = "backend" | "worker";

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  logger: string;
  message: string;
  component: LogComponent;
}

export interface AdminStats {
  total: number;
  done: number;
  processing: number;
  failed: number;
  pending: number;
  recent: Magazine[];
}
