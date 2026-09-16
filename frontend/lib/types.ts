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
  // Distinguait un tag de sujet (« Bricolage ») d'un format éditorial
  // (« Test »), pour ne propager que les premiers vers le thémage par numéro.
  // Cette propagation ayant été retirée, le champ n'a plus de consommateur :
  // tous les tags sont proposés comme filtres de recherche. Conservé parce
  // que l'API le renvoie toujours et que la colonne existe en base.
  is_subject: boolean;
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
  updated_at: string;
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
  magazine_issue_month: string | null;
  magazine_publication_date: string | null;
  magazine_collection_name: string | null;
}

export interface SubthemeReportLine {
  // Thématique de rattachement — la taxonomie étant désormais globale, un
  // compte rendu couvre plusieurs thématiques à la fois.
  thematique: string;
  nom: string;
  // Nombre d'ARTICLES rattachés, et non de numéros : c'est l'article qui
  // relève d'une sous-thématique, pas le numéro qui le contient.
  articles: number;
  // Mots-clés ne correspondant à aucun article : signalent un regroupement
  // inventé par le modèle, absent du corpus réel.
  mots_cles_steriles: string[];
}

export interface SubthemeImportReport {
  applique: boolean;
  articles_corpus: number;
  articles_couverts: number;
  articles_sans_sous_thematique: number;
  thematiques: number;
  sous_thematiques: SubthemeReportLine[];
  entrees_ignorees: string[];
}

// Niveau 1 de la taxonomie. Le comptage porte sur les ARTICLES rattachés par
// mots-clés ; l'ancien comptage par NUMÉRO, hérité des étiquettes Gemini, a
// été retiré avec ses endpoints.
export interface TaxonomyTheme {
  id: number;
  name: string;
  subtheme_count: number;
  article_count: number;
}

// Niveau 2.
export interface Subtheme {
  id: number;
  name: string;
  article_count: number;
}

export interface SubthemeArticle {
  id: number;
  title: string;
  start_page: number;
  magazine_id: number;
  magazine_title: string;
  issue_number: string | null;
  issue_month_label: string | null;
  publication_date: string | null;
}

// Niveau 3 : les articles d'une sous-thématique, regroupés par collection.
export interface SubthemeCollectionGroup {
  collection_id: number | null;
  collection_name: string | null;
  article_count: number;
  articles: SubthemeArticle[];
}

// Articles qu'aucune sous-thématique n'attrape, et mots qui y reviennent.
// Sert à enrichir la taxonomie sans appel à un modèle : un terme fréquent
// parmi les orphelins et absent des mots-clés se repère à l'œil.
export interface Orphans {
  articles_total: number;
  articles_orphelins: number;
  mots_frequents: { mot: string; occurrences: number }[];
  exemples: string[];
}

// Volumétrie du corpus à soumettre au modèle externe. Affichée avant le
// téléchargement : c'est elle qui dit si l'export tiendra dans une seule
// invite ou s'il faudra le livrer en plusieurs fois.
export interface CorpusExport {
  articles: number;
  collections: number;
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
  publication_date: string | null;
  issue_number: string | null;
  issue_month: string | null;
  collection_name: string | null;
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
  /** Nombre total d'articles extraits des sommaires. */
  articles_total: number;
  /** Articles DISTINCTS rattaches a au moins une sous-thematique. Le reste
   *  a faire se deduit par soustraction, pour eviter deux valeurs qui
   *  pourraient diverger. */
  articles_rattaches: number;
  recent: Magazine[];
}
