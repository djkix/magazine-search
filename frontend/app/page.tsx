"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";
import SearchBar, { type SearchFilters } from "@/components/SearchBar";
import ResultCard from "@/components/ResultCard";

export default function SearchPage() {
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  async function runSearch(filters: SearchFilters) {
    setLoading(true);
    setError(null);
    setQuery(filters.q);
    const params = new URLSearchParams({ q: filters.q });
    if (filters.magazine_title) params.set("magazine_title", filters.magazine_title);
    if (filters.year) params.set("year", filters.year);
    if (filters.issue_number) params.set("issue_number", filters.issue_number);

    try {
      const data = await api.get<SearchResponse>(`/search?${params.toString()}`);
      setResults(data);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        window.location.href = "/login";
        return;
      }
      setError(err instanceof ApiError ? err.message : "Erreur de recherche");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <SearchBar onSearch={runSearch} />

      {loading && <p className="text-sm text-slate-500">Recherche en cours...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {results && !loading && (
        <div className="space-y-3">
          <p className="text-sm text-slate-500">
            {results.total_hits} résultat{results.total_hits !== 1 ? "s" : ""} ({results.processing_time_ms} ms)
          </p>
          {results.hits.map((hit) => (
            <ResultCard key={`${hit.page_id}`} hit={hit} query={query} />
          ))}
        </div>
      )}
    </div>
  );
}
