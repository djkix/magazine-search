"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { ArticleWithMagazine, Category } from "@/lib/types";
import PageContainer from "@/components/layout/PageContainer";
import Icon from "@/components/ui/Icon";

export default function ArticlesPage() {
  const [q, setQ] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [categories, setCategories] = useState<Category[]>([]);
  const [articles, setArticles] = useState<ArticleWithMagazine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Category[]>("/categories").then(setCategories).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({ limit: "200" });
    if (q.trim()) params.set("q", q.trim());
    if (categoryId) params.set("category_id", categoryId);
    const timeout = setTimeout(() => {
      api
        .get<ArticleWithMagazine[]>(`/articles?${params.toString()}`)
        .then(setArticles)
        .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur"))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(timeout);
  }, [q, categoryId]);

  const groups = useMemo(() => {
    const byMagazine = new Map<number, { title: string; issueNumber: string | null; articles: ArticleWithMagazine[] }>();
    for (const article of articles) {
      const existing = byMagazine.get(article.magazine_id);
      if (existing) {
        existing.articles.push(article);
      } else {
        byMagazine.set(article.magazine_id, {
          title: article.magazine_title,
          issueNumber: article.magazine_issue_number,
          articles: [article],
        });
      }
    }
    return Array.from(byMagazine.entries());
  }, [articles]);

  return (
    <PageContainer>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-semibold text-foreground">Sommaires — tous les articles</h1>
        <div className="flex flex-col gap-3 sm:flex-row">
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
          <div className="relative w-full sm:w-80">
            <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-foreground-muted" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Rechercher un article..."
              className="w-full rounded-xl border border-outline-variant bg-surface py-2 pl-10 pr-3 text-sm text-foreground outline-none transition focus:border-primary"
            />
          </div>
        </div>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="space-y-6">
        {groups.map(([magazineId, group]) => (
          <div key={magazineId} className="overflow-hidden rounded-xl border border-outline-variant">
            <div className="bg-surface-hover px-4 py-3">
              <Link href={`/viewer/${magazineId}/1`} className="text-sm font-semibold text-foreground hover:text-primary-light">
                {group.title}
                {group.issueNumber ? ` — ${group.issueNumber}` : ""}
              </Link>
            </div>
            <ul className="divide-y divide-outline-variant">
              {group.articles.map((article) => (
                <li key={article.id}>
                  <Link
                    href={`/viewer/${article.magazine_id}/${article.start_page}`}
                    className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm text-foreground hover:bg-surface/60 hover:text-primary-light"
                  >
                    <span className="min-w-0 truncate">{article.title}</span>
                    <span className="shrink-0 font-mono text-xs text-foreground-muted">
                      p.{article.start_page}
                      {article.end_page && article.end_page !== article.start_page ? `–${article.end_page}` : ""}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
        {!loading && groups.length === 0 && (
          <p className="py-8 text-center text-sm text-foreground-muted">Aucun article trouvé.</p>
        )}
      </div>
    </PageContainer>
  );
}
