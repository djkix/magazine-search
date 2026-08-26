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

export interface Magazine {
  id: number;
  title: string;
  issue_number: string | null;
  publication_date: string | null;
  filename: string;
  cover_thumbnail_path: string | null;
  scan_status: "detected" | "stable" | "queued" | "processing" | "done" | "failed";
  error_message: string | null;
  created_at: string;
  file_size: number;
  page_count: number;
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

export interface AdminStats {
  total: number;
  done: number;
  processing: number;
  failed: number;
  pending: number;
  recent: Magazine[];
}
