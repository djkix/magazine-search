"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { ArticleWithMagazine } from "@/lib/types";
import PageContainer from "@/components/layout/PageContainer";
import Icon from "@/components/ui/Icon";

export default function ArticlesPage() {
  const [q, setQ] = useState("");
  const [articles, setArticles] = useState<ArticleWithMagazine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({ limit: "100" });
    if (q.trim()) params.set("q", q.trim());
    const timeout = setTimeout(() => {
      api
        .get<ArticleWithMagazine[]>(`/articles?${params.toString()}`)
        .then(setArticles)
        .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur"))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(timeout);
  }, [q]);

  return (
    <PageContainer>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-semibold text-foreground">Sommaires — tous les articles</h1>
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

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="overflow-hidden rounded-xl border border-outline-variant">
        <table className="w-full text-sm">
          <thead className="bg-surface-hover text-left font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
            <tr>
              <th className="px-4 py-3">Article</th>
              <th className="px-4 py-3">Magazine</th>
              <th className="px-4 py-3">Page</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant">
            {articles.map((article) => (
              <tr key={article.id} className="bg-surface/40">
                <td className="px-4 py-3 text-foreground">
                  <Link
                    href={`/viewer/${article.magazine_id}/${article.start_page}`}
                    className="hover:text-primary-light hover:underline"
                  >
                    {article.title}
                  </Link>
                </td>
                <td className="px-4 py-3 text-foreground-muted">
                  {article.magazine_title}
                  {article.magazine_issue_number ? ` — ${article.magazine_issue_number}` : ""}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-foreground-muted">
                  {article.start_page}
                  {article.end_page && article.end_page !== article.start_page ? `–${article.end_page}` : ""}
                </td>
              </tr>
            ))}
            {!loading && articles.length === 0 && (
              <tr>
                <td colSpan={3} className="px-4 py-8 text-center text-foreground-muted">
                  Aucun article trouvé.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </PageContainer>
  );
}
