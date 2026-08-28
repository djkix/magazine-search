"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { LibraryOverview, Tag } from "@/lib/types";
import Icon from "@/components/ui/Icon";

export interface SearchFilters {
  q: string;
  magazine_title?: string;
  year?: string;
  issue_number?: string;
  collection_ids?: string[];
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
  const [selectedCollectionIds, setSelectedCollectionIds] = useState<Set<number>>(
    new Set((initial?.collection_ids ?? []).map(Number))
  );
  const [activeTagId, setActiveTagId] = useState<number | null>(null);
  const [tags, setTags] = useState<Tag[]>([]);
  const [collections, setCollections] = useState<LibraryOverview["collections"]>([]);
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    api.get<Tag[]>("/tags").then(setTags).catch(() => {});
    api
      .get<LibraryOverview>("/collections")
      .then((overview) => setCollections(overview.collections))
      .catch(() => {});
  }, []);

  function toggleCollection(id: number) {
    setSelectedCollectionIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    onSearch({
      q: q.trim(),
      magazine_title: magazineTitle.trim() || undefined,
      year: year.trim() || undefined,
      issue_number: issueNumber.trim() || undefined,
      collection_ids: selectedCollectionIds.size > 0 ? Array.from(selectedCollectionIds, String) : undefined,
    });
  }

  const activeTagCollections = collections.filter((c) => c.tags.some((t) => t.id === activeTagId));

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

      {tags.length > 0 && (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-1.5">
            {tags.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setActiveTagId((prev) => (prev === t.id ? null : t.id))}
                className={`rounded-full px-3 py-1 text-xs transition ${
                  activeTagId === t.id ? "bg-primary/20 text-primary-light" : "bg-surface text-foreground-muted hover:bg-surface-hover"
                }`}
              >
                {t.name}
              </button>
            ))}
          </div>

          {activeTagId !== null && activeTagCollections.length > 0 && (
            <div className="flex flex-wrap gap-1.5 rounded-xl border border-outline-variant bg-surface/40 p-2.5">
              {activeTagCollections.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => toggleCollection(c.id)}
                  className={`rounded-full px-2.5 py-1 text-[11px] transition ${
                    selectedCollectionIds.has(c.id)
                      ? "bg-primary text-white"
                      : "bg-surface text-foreground-muted hover:bg-surface-hover"
                  }`}
                >
                  {c.name}
                </button>
              ))}
            </div>
          )}

          {selectedCollectionIds.size > 0 && (
            <p className="text-xs text-foreground-muted">
              Recherche limitée à {selectedCollectionIds.size} collection{selectedCollectionIds.size > 1 ? "s" : ""} —{" "}
              <button type="button" onClick={() => setSelectedCollectionIds(new Set())} className="text-primary-light hover:underline">
                réinitialiser
              </button>
            </p>
          )}
        </div>
      )}

      {showFilters && (
        <div className="flex flex-wrap gap-2 rounded-xl border border-outline-variant bg-surface/40 p-3">
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
