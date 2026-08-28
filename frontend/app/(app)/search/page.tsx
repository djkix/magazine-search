"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";
import PageContainer from "@/components/layout/PageContainer";
import SearchBar, { type SearchFilters } from "@/components/search/SearchBar";
import ResultCard from "@/components/search/ResultCard";
import Icon from "@/components/ui/Icon";

export default function SearchResultsPage() {
  return (
    <Suspense
      fallback={
        <PageContainer>
          <p className="text-sm text-foreground-muted">Chargement...</p>
        </PageContainer>
      }
    >
      <SearchResultsContent />
    </Suspense>
  );
}

function SearchResultsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const q = searchParams.get("q") ?? "";

  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!q) return;
    setLoading(true);
    setError(null);
    api
      .get<SearchResponse>(`/search?${searchParams.toString()}`)
      .then(setResults)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          window.location.href = "/login";
          return;
        }
        setError(err instanceof ApiError ? err.message : "Erreur de recherche");
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams.toString()]);

  function runSearch(filters: SearchFilters) {
    const params = new URLSearchParams({ q: filters.q });
    if (filters.magazine_title) params.set("magazine_title", filters.magazine_title);
    if (filters.year) params.set("year", filters.year);
    if (filters.issue_number) params.set("issue_number", filters.issue_number);
    for (const id of filters.collection_ids ?? []) params.append("collection_id", id);
    router.push(`/search?${params.toString()}`);
  }

  return (
    <PageContainer>
      <div className="mb-8">
        <SearchBar onSearch={runSearch} initial={{ q, collection_ids: searchParams.getAll("collection_id") }} />
      </div>

      {loading && <p className="text-sm text-foreground-muted">Recherche en cours...</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}

      {results && !loading && (
        <div className="space-y-4">
          <p className="font-mono text-xs uppercase tracking-wider text-foreground-muted">
            {results.total_hits} résultat{results.total_hits !== 1 ? "s" : ""} · {results.processing_time_ms} ms
          </p>

          {results.hits.length === 0 && (
            <div className="flex flex-col items-center gap-3 rounded-xl border border-outline-variant bg-surface/40 py-16 text-center">
              <Icon name="search_off" className="text-3xl text-foreground-muted" />
              <p className="text-sm text-foreground-muted">Aucun résultat pour « {q} ».</p>
            </div>
          )}

          <div className="space-y-3">
            {results.hits.map((hit) => (
              <ResultCard key={hit.page_id} hit={hit} query={q} />
            ))}
          </div>
        </div>
      )}
    </PageContainer>
  );
}
