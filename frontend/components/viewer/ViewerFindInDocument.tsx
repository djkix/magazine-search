"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { SearchHit, SearchResponse } from "@/lib/types";
import Icon from "@/components/ui/Icon";

export default function ViewerFindInDocument({
  magazineId,
  onSelectHit,
}: {
  magazineId: number;
  onSelectHit: (hit: SearchHit) => void;
}) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runSearch() {
    const term = q.trim();
    if (!term) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<SearchResponse>(
        `/search?q=${encodeURIComponent(term)}&magazine_id=${magazineId}&limit=100`
      );
      setHits(data.hits);
      setIndex(0);
      if (data.hits.length > 0) onSelectHit(data.hits[0]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur de recherche");
      setHits(null);
    } finally {
      setLoading(false);
    }
  }

  function step(delta: number) {
    if (!hits || hits.length === 0) return;
    const next = (index + delta + hits.length) % hits.length;
    setIndex(next);
    onSelectHit(hits[next]);
  }

  return (
    <div className="border-b border-outline-variant p-4">
      <p className="mb-3 font-mono text-xs uppercase tracking-wider text-foreground-muted">Rechercher dans ce numéro</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          runSearch();
        }}
        className="flex gap-2"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Un mot..."
          className="w-full rounded-xl border border-outline-variant bg-surface px-3 py-2 text-sm text-foreground outline-none transition focus:border-primary"
        />
        <button
          type="submit"
          disabled={loading}
          className="shrink-0 rounded-xl bg-primary/10 px-3 text-primary-light transition hover:bg-primary/20 disabled:opacity-50"
        >
          <Icon name="search" />
        </button>
      </form>

      {loading && <p className="mt-2 text-xs text-foreground-muted">Recherche...</p>}
      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}

      {hits && !loading && (
        <div className="mt-3 flex items-center justify-between">
          <span className="font-mono text-xs text-foreground-muted">
            {hits.length === 0
              ? "Aucun résultat"
              : `Page ${hits[index].page_number} · ${index + 1} / ${hits.length}`}
          </span>
          {hits.length > 1 && (
            <div className="flex gap-1">
              <button
                type="button"
                onClick={() => step(-1)}
                className="rounded-lg border border-outline-variant p-1.5 text-foreground-muted transition hover:border-primary hover:text-foreground"
                aria-label="Occurrence précédente"
              >
                <Icon name="chevron_left" className="text-base" />
              </button>
              <button
                type="button"
                onClick={() => step(1)}
                className="rounded-lg border border-outline-variant p-1.5 text-foreground-muted transition hover:border-primary hover:text-foreground"
                aria-label="Occurrence suivante"
              >
                <Icon name="chevron_right" className="text-base" />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
