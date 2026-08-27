"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { ArticleWithMagazine, LibraryOverview } from "@/lib/types";
import PageContainer from "@/components/layout/PageContainer";
import Icon from "@/components/ui/Icon";

export default function CollectionArticlesPage() {
  const params = useParams<{ collectionId: string }>();
  const collectionId = params.collectionId;
  const isUnassigned = collectionId === "none";

  const [name, setName] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [articles, setArticles] = useState<ArticleWithMagazine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({ limit: "200" });
    if (q.trim()) params.set("q", q.trim());
    if (isUnassigned) {
      params.set("unassigned", "true");
    } else {
      params.set("collection_id", collectionId);
    }
    const timeout = setTimeout(() => {
      api
        .get<ArticleWithMagazine[]>(`/articles?${params.toString()}`)
        .then(setArticles)
        .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur"))
        .finally(() => setLoading(false));
    }, 250);
    return () => clearTimeout(timeout);
  }, [q, collectionId, isUnassigned]);

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
        <div>
          <Link href="/articles" className="inline-flex items-center gap-1 text-sm text-foreground-muted hover:text-foreground">
            <Icon name="arrow_back" className="text-base" />
            Sommaires
          </Link>
          <h1 className="mt-2 text-xl font-semibold text-foreground">{name ?? "..."}</h1>
        </div>
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
