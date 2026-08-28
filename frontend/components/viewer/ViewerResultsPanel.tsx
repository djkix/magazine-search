"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { SearchHit, SearchResponse } from "@/lib/types";
import { sanitizeHighlightedSnippet } from "@/lib/sanitize";
import { occurrenceColorRgb } from "@/lib/occurrenceColor";
import Icon from "@/components/ui/Icon";

export default function ViewerResultsPanel({
  magazineId,
  searchParamsString,
  onSelectSameMagazineHit,
}: {
  magazineId: number;
  searchParamsString: string;
  onSelectSameMagazineHit: (hit: SearchHit) => void;
}) {
  const router = useRouter();
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .get<SearchResponse>(`/search?${searchParamsString}`)
      .then(setResults)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur de recherche"))
      .finally(() => setLoading(false));
  }, [searchParamsString]);

  const maxOccurrence = Math.max(0, ...(results?.hits.map((h) => h.occurrence_count) ?? []));

  return (
    <div className="flex h-full flex-col p-4">
      <p className="mb-3 font-mono text-xs uppercase tracking-wider text-foreground-muted">
        Résultats de recherche{results ? ` · ${results.total_hits}` : ""}
      </p>

      {loading && <p className="text-sm text-foreground-muted">Chargement...</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="flex-1 space-y-2 overflow-y-auto">
        {results?.hits.map((hit) => {
          const isCurrent = hit.magazine_id === magazineId;
          const rgb = occurrenceColorRgb(hit.occurrence_count, maxOccurrence);
          return (
            <button
              key={hit.magazine_id}
              onClick={() => {
                if (isCurrent) onSelectSameMagazineHit(hit);
                else router.push(`/viewer/${hit.magazine_id}/${hit.page_number}?${searchParamsString}`);
              }}
              className={`block w-full rounded-xl border p-3 text-left text-sm transition ${
                isCurrent ? "border-primary bg-primary/5" : "border-outline-variant bg-surface/50 hover:border-primary"
              }`}
            >
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="min-w-0 truncate font-serif text-sm font-semibold text-foreground">
                  {hit.magazine_title}
                </span>
                <span
                  className="shrink-0 rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider"
                  style={{ color: `rgb(${rgb})`, backgroundColor: `rgba(${rgb}, 0.15)` }}
                >
                  {hit.occurrence_count}
                </span>
              </div>
              <p className="mb-1 flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
                <Icon name="description" className="text-xs" />
                Page {hit.page_number}
              </p>
              <p
                className="line-clamp-3 text-foreground-muted"
                dangerouslySetInnerHTML={{ __html: sanitizeHighlightedSnippet(hit.snippet) }}
              />
            </button>
          );
        })}
        {!loading && results?.hits.length === 0 && <p className="text-sm text-foreground-muted">Aucun résultat.</p>}
      </div>
    </div>
  );
}
