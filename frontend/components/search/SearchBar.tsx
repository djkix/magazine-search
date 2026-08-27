"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Category, LibraryOverview } from "@/lib/types";
import Icon from "@/components/ui/Icon";

export interface SearchFilters {
  q: string;
  magazine_title?: string;
  year?: string;
  issue_number?: string;
  category_id?: string;
  collection_id?: string;
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
  const [categoryId, setCategoryId] = useState(initial?.category_id ?? "");
  const [collectionId, setCollectionId] = useState(initial?.collection_id ?? "");
  const [categories, setCategories] = useState<Category[]>([]);
  const [collections, setCollections] = useState<LibraryOverview["collections"]>([]);
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    api.get<Category[]>("/categories").then(setCategories).catch(() => {});
    api
      .get<LibraryOverview>("/collections")
      .then((overview) => setCollections(overview.collections))
      .catch(() => {});
  }, []);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    onSearch({
      q: q.trim(),
      magazine_title: magazineTitle.trim() || undefined,
      year: year.trim() || undefined,
      issue_number: issueNumber.trim() || undefined,
      category_id: categoryId || undefined,
      collection_id: collectionId || undefined,
    });
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="flex items-center gap-2 rounded-xl border border-outline-variant bg-surface/60 p-2 pl-4 backdrop-blur-sm transition focus-within:border-primary">
        <Icon name="search" className="text-foreground-muted" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Rechercher..."
          className="flex-1 bg-transparent py-2.5 text-sm text-foreground outline-none placeholder:text-foreground-muted/60"
        />
        <button
          type="button"
          onClick={() => setShowFilters((v) => !v)}
          className={`rounded-lg p-2 transition ${
            showFilters ? "bg-primary/10 text-primary-light" : "text-foreground-muted hover:bg-surface-hover"
          }`}
        >
          <Icon name="tune" />
        </button>
        <button
          type="submit"
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white transition hover:bg-primary/90"
        >
          Rechercher
        </button>
      </div>

      {showFilters && (
        <div className="flex flex-wrap gap-2 rounded-xl border border-outline-variant bg-surface/40 p-3">
          {categories.length > 0 && (
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="rounded-lg border border-outline-variant bg-surface px-3 py-1.5 text-sm text-foreground"
            >
              <option value="">Toutes les catégories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
          {collections.length > 0 && (
            <select
              value={collectionId}
              onChange={(e) => setCollectionId(e.target.value)}
              className="rounded-lg border border-outline-variant bg-surface px-3 py-1.5 text-sm text-foreground"
            >
              <option value="">Toutes les collections</option>
              {collections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
          <input
            value={magazineTitle}
            onChange={(e) => setMagazineTitle(e.target.value)}
            placeholder="Titre du magazine"
            className="flex-1 rounded-lg border border-outline-variant bg-surface px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary"
          />
          <input
            value={year}
            onChange={(e) => setYear(e.target.value)}
            placeholder="Année"
            className="w-28 rounded-lg border border-outline-variant bg-surface px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary"
          />
          <input
            value={issueNumber}
            onChange={(e) => setIssueNumber(e.target.value)}
            placeholder="Numéro"
            className="w-28 rounded-lg border border-outline-variant bg-surface px-3 py-1.5 text-sm text-foreground outline-none focus:border-primary"
          />
        </div>
      )}
    </form>
  );
}
