"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { LibraryOverview, Magazine } from "@/lib/types";
import PageContainer from "@/components/layout/PageContainer";
import MagazineCard from "@/components/library/MagazineCard";
import Icon from "@/components/ui/Icon";

const PAGE_SIZE = 100;
const ISSUE_TYPE_ORDER: Record<Magazine["issue_type"], number> = { normal: 0, hs: 1, sp: 2 };

export default function CollectionLibraryPage() {
  const params = useParams<{ collectionId: string }>();
  const collectionId = params.collectionId;
  const isUnassigned = collectionId === "none";

  const [name, setName] = useState<string | null>(null);
  const [items, setItems] = useState<Magazine[]>([]);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [yearFilter, setYearFilter] = useState<number | null>(null);
  const [sortMode, setSortMode] = useState<"date" | "type">("date");

  useEffect(() => {
    if (isUnassigned) {
      setName("Sans collection");
      return;
    }
    api
      .get<LibraryOverview>("/collections")
      .then((overview) => {
        const match = overview.collections.find((c) => String(c.id) === collectionId);
        setName(match?.name ?? null);
      })
      .catch(() => {});
  }, [collectionId, isUnassigned]);

  async function loadPage(targetPage: number) {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(targetPage), limit: String(PAGE_SIZE) });
      if (isUnassigned) {
        params.set("unassigned", "true");
      } else {
        params.set("collection_id", collectionId);
      }
      if (yearFilter) params.set("year", String(yearFilter));
      const data = await api.get<Magazine[]>(`/magazines?${params.toString()}`);
      setItems((prev) => (targetPage === 0 ? data : [...prev, ...data]));
      setHasMore(data.length === PAGE_SIZE);
      setPage(targetPage);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) window.location.href = "/login";
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPage(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionId, yearFilter]);

  const sortedItems = useMemo(() => {
    if (sortMode === "date") return items;
    return [...items].sort((a, b) => {
      const typeDiff = ISSUE_TYPE_ORDER[a.issue_type] - ISSUE_TYPE_ORDER[b.issue_type];
      if (typeDiff !== 0) return typeDiff;
      return (b.publication_date ?? "").localeCompare(a.publication_date ?? "");
    });
  }, [items, sortMode]);

  return (
    <PageContainer>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Link href="/library" className="inline-flex items-center gap-1 text-sm text-foreground-muted hover:text-foreground">
            <Icon name="arrow_back" className="text-base" />
            Bibliothèque
          </Link>
          <h1 className="mt-2 text-2xl font-semibold text-foreground">{name ?? "..."}</h1>
        </div>
        <div className="flex items-center gap-2">
          {yearFilter && (
            <button
              onClick={() => setYearFilter(null)}
              className="flex items-center gap-1 rounded-full bg-primary/20 px-3 py-1.5 text-xs text-primary-light"
            >
              {yearFilter}
              <Icon name="close" className="text-sm" />
            </button>
          )}
          <select
            value={sortMode}
            onChange={(e) => setSortMode(e.target.value as "date" | "type")}
            className="rounded-xl border border-outline-variant bg-surface px-3 py-2 text-sm text-foreground"
          >
            <option value="date">Trier par date</option>
            <option value="type">Trier par type</option>
          </select>
        </div>
      </div>

      {items.length === 0 && !loading && <p className="text-sm text-foreground-muted">Aucun magazine dans cette collection.</p>}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {sortedItems.map((m) => (
          <MagazineCard key={m.id} magazine={m} onYearClick={setYearFilter} />
        ))}
      </div>

      {hasMore && (
        <div className="mt-8 flex justify-center">
          <button
            onClick={() => loadPage(page + 1)}
            disabled={loading}
            className="rounded-xl border border-outline-variant px-5 py-2.5 text-sm text-foreground transition hover:border-primary disabled:opacity-50"
          >
            {loading ? "Chargement..." : "Charger plus"}
          </button>
        </div>
      )}
    </PageContainer>
  );
}
