const HTML_ESCAPES: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
};

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
}

/**
 * Meilisearch snippets contain raw, unescaped document text (extracted from PDFs we
 * don't control the content of) plus our own <mark>/</mark> highlight tags. Escape
 * everything except those two literal tags before using dangerouslySetInnerHTML, so
 * PDF text can never inject arbitrary HTML/script.
 */
export function sanitizeHighlightedSnippet(raw: string): string {
  return raw
    .split(/(<mark>|<\/mark>)/g)
    .map((part) => (part === "<mark>" || part === "</mark>" ? part : escapeHtml(part)))
    .join("");
}
