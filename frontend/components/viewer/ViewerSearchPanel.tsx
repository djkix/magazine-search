"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { SearchHit, SearchResponse } from "@/lib/types";
import { sanitizeHighlightedSnippet } from "@/lib/sanitize";
import Icon from "@/components/ui/Icon";

export default function ViewerSearchPanel({
  magazineId,
  initialQuery,
  currentPage,
  onSelectHit,
}: {
  magazineId: number;
  initialQuery?: string;
  currentPage: number;
  onSelectHit: (hit: SearchHit) => void;
}) {
  const [q, setQ] = useState(initialQuery ?? "");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runSearch(term: string, autoSelectCurrent = false) {
    if (!term.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<SearchResponse>(
        `/search?q=${encodeURIComponent(term.trim())}&magazine_id=${magazineId}&limit=50`
      );
      setHits(data.hits);
      if (autoSelectCurrent) {
        const currentHit = data.hits.find((h) => h.page_number === currentPage);
        if (currentHit) onSelectHit(currentHit);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur de recherche");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (initialQuery) runSearch(initialQuery, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery]);

  return (
    <div className="flex h-full flex-col p-4">
      <p className="mb-3 font-mono text-xs uppercase tracking-wider text-foreground-muted">Recherche dans le document</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          runSearch(q);
        }}
        className="mb-4 flex gap-2"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Rechercher dans ce numéro..."
          className="w-full rounded-xl border border-outline-variant bg-surface px-3 py-2 text-sm text-foreground outline-none transition focus:border-primary"
        />
        <button
          type="submit"
          className="rounded-xl bg-primary/10 px-3 text-primary-light transition hover:bg-primary/20"
        >
          <Icon name="search" />
        </button>
      </form>

      {loading && <p className="text-sm text-foreground-muted">Recherche...</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="flex-1 space-y-2 overflow-y-auto">
        {hits?.length === 0 && <p className="text-sm text-foreground-muted">Aucun résultat.</p>}
        {hits?.map((hit) => (
          <button
            key={hit.page_id}
            onClick={() => onSelectHit(hit)}
            className={`block w-full rounded-xl border p-3 text-left text-sm transition ${
              hit.page_number === currentPage
                ? "border-primary bg-primary/5"
                : "border-outline-variant bg-surface/50 hover:border-primary"
            }`}
          >
            <p className="mb-1 font-mono text-[10px] uppercase tracking-wider text-foreground-muted">Page {hit.page_number}</p>
            <p
              className="line-clamp-3 text-foreground"
              dangerouslySetInnerHTML={{ __html: sanitizeHighlightedSnippet(hit.snippet) }}
            />
          </button>
        ))}
      </div>
    </div>
  );
}
