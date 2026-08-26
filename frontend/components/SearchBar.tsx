"use client";

import { useState } from "react";

export interface SearchFilters {
  q: string;
  magazine_title?: string;
  year?: string;
  issue_number?: string;
}

export default function SearchBar({
  onSearch,
  initial,
}: {
  onSearch: (filters: SearchFilters) => void;
  initial?: SearchFilters;
}) {
  const [q, setQ] = useState(initial?.q ?? "");
  const [magazineTitle, setMagazineTitle] = useState(initial?.magazine_title ?? "");
  const [year, setYear] = useState(initial?.year ?? "");
  const [issueNumber, setIssueNumber] = useState(initial?.issue_number ?? "");
  const [showFilters, setShowFilters] = useState(false);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    onSearch({
      q: q.trim(),
      magazine_title: magazineTitle.trim() || undefined,
      year: year.trim() || undefined,
      issue_number: issueNumber.trim() || undefined,
    });
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      <div className="flex gap-2">
        <input
          type="text"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Rechercher dans les magazines..."
          className="flex-1 rounded border px-4 py-2 text-sm"
        />
        <button type="submit" className="rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700">
          Rechercher
        </button>
        <button
          type="button"
          onClick={() => setShowFilters((v) => !v)}
          className="rounded border px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
        >
          Filtres
        </button>
      </div>
      {showFilters && (
        <div className="flex gap-2 rounded border bg-white p-3">
          <input
            type="text"
            value={magazineTitle}
            onChange={(e) => setMagazineTitle(e.target.value)}
            placeholder="Titre du magazine"
            className="flex-1 rounded border px-3 py-1.5 text-sm"
          />
          <input
            type="text"
            value={year}
            onChange={(e) => setYear(e.target.value)}
            placeholder="Année"
            className="w-28 rounded border px-3 py-1.5 text-sm"
          />
          <input
            type="text"
            value={issueNumber}
            onChange={(e) => setIssueNumber(e.target.value)}
            placeholder="Numéro"
            className="w-28 rounded border px-3 py-1.5 text-sm"
          />
        </div>
      )}
    </form>
  );
}
