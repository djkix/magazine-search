"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Category, Magazine } from "@/lib/types";
import PageContainer from "@/components/layout/PageContainer";
import MagazineCard from "@/components/library/MagazineCard";

const PAGE_SIZE = 24;

export default function LibraryPage() {
  const [items, setItems] = useState<Magazine[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryId, setCategoryId] = useState("");
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get<Category[]>("/categories").then(setCategories).catch(() => {});
  }, []);

  async function loadPage(targetPage: number) {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(targetPage), limit: String(PAGE_SIZE) });
      if (categoryId) params.set("category_id", categoryId);
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
  }, [categoryId]);

  return (
    <PageContainer>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Bibliothèque</h1>
        {categories.length > 0 && (
          <select
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            className="rounded-xl border border-outline-variant bg-surface px-3 py-2 text-sm text-foreground"
          >
            <option value="">Toutes les catégories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {items.length === 0 && !loading && <p className="text-sm text-foreground-muted">Aucun magazine indexé pour le moment.</p>}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {items.map((m) => (
          <MagazineCard key={m.id} magazine={m} />
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
