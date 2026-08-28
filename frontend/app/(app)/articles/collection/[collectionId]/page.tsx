"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { Article, ArticleWithMagazine, LibraryOverview, Magazine, MagazineTheme } from "@/lib/types";
import { useUser } from "@/components/layout/UserContext";
import PageContainer from "@/components/layout/PageContainer";
import MagazineCard from "@/components/library/MagazineCard";
import Icon from "@/components/ui/Icon";

const PAGE_SIZE_OPTIONS = ["10", "20", "50", "all"] as const;
type PageSizeOption = (typeof PAGE_SIZE_OPTIONS)[number];

export default function CollectionArticlesPage() {
  const params = useParams<{ collectionId: string }>();
  const collectionId = params.collectionId;
  const isUnassigned = collectionId === "none";
  const user = useUser();

  const [name, setName] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [viewMode, setViewMode] = useState<"number" | "theme">("number");

  // "Par numéro": paginated by magazine.
  const [pageSize, setPageSize] = useState<PageSizeOption>("20");
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [magazines, setMagazines] = useState<Magazine[]>([]);
  const [articlesByMagazine, setArticlesByMagazine] = useState<Map<number, Article[]>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Free-text search falls back to a flat, unpaginated article search.
  const [searchResults, setSearchResults] = useState<ArticleWithMagazine[] | null>(null);
  const [searching, setSearching] = useState(false);

  // "Par thématique".
  const [themes, setThemes] = useState<MagazineTheme[]>([]);
  const [themesLoading, setThemesLoading] = useState(false);
  const [selectedTheme, setSelectedTheme] = useState<MagazineTheme | null>(null);
  const [themeMagazines, setThemeMagazines] = useState<Magazine[]>([]);
  const [themeMagazinesLoading, setThemeMagazinesLoading] = useState(false);

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

  function collectionParams(extra: Record<string, string> = {}) {
    const params = new URLSearchParams(extra);
    if (isUnassigned) params.set("unassigned", "true");
    else params.set("collection_id", collectionId);
    return params;
  }

  // Free-text search (flat, article-level, unpaginated).
  useEffect(() => {
    if (!q.trim()) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    const params = collectionParams({ limit: "200", q: q.trim() });
    const timeout = setTimeout(() => {
      api
        .get<ArticleWithMagazine[]>(`/articles?${params.toString()}`)
        .then(setSearchResults)
        .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur"))
        .finally(() => setSearching(false));
    }, 250);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, collectionId, isUnassigned]);

  // Paginated "par numéro" browse (only relevant while not searching).
  useEffect(() => {
    if (viewMode !== "number" || q.trim()) return;
    setLoading(true);
    setError(null);
    const limit = pageSize === "all" ? "1000" : pageSize;
    const magParams = collectionParams({ page: pageSize === "all" ? "0" : String(page), limit });
    const countParams = collectionParams();

    Promise.all([
      api.get<Magazine[]>(`/magazines?${magParams.toString()}`),
      api.get<{ total: number }>(`/magazines/count?${countParams.toString()}`),
    ])
      .then(async ([mags, countRes]) => {
        setMagazines(mags);
        setTotal(countRes.total);
        const entries = await Promise.all(
          mags.map((m) =>
            api
              .get<Article[]>(`/magazines/${m.id}/articles`)
              .then((a): [number, Article[]] => [m.id, a])
              .catch((): [number, Article[]] => [m.id, []])
          )
        );
        setArticlesByMagazine(new Map(entries));
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode, collectionId, isUnassigned, page, pageSize, q]);

  useEffect(() => {
    setPage(0);
  }, [pageSize, collectionId]);

  // "Par thématique".
  useEffect(() => {
    if (viewMode !== "theme" || isUnassigned) return;
    setThemesLoading(true);
    setSelectedTheme(null);
    api
      .get<MagazineTheme[]>(`/collections/${collectionId}/themes`)
      .then(setThemes)
      .catch(() => setThemes([]))
      .finally(() => setThemesLoading(false));
  }, [viewMode, collectionId, isUnassigned]);

  useEffect(() => {
    if (!selectedTheme) return;
    setThemeMagazinesLoading(true);
    const p = collectionParams({ theme_id: String(selectedTheme.id), limit: "100" });
    api
      .get<Magazine[]>(`/magazines?${p.toString()}`)
      .then(setThemeMagazines)
      .catch(() => setThemeMagazines([]))
      .finally(() => setThemeMagazinesLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTheme]);

  const groups = useMemo(() => {
    return magazines.map((m) => ({ magazine: m, articles: articlesByMagazine.get(m.id) ?? [] }));
  }, [magazines, articlesByMagazine]);

  const totalPages = pageSize === "all" ? 1 : Math.max(1, Math.ceil(total / Number(pageSize)));

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
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          {!isUnassigned && (
            <div className="flex rounded-xl border border-outline-variant bg-surface p-1 text-sm">
              <button
                onClick={() => setViewMode("number")}
                className={`rounded-lg px-3 py-1.5 transition ${
                  viewMode === "number" ? "bg-primary/10 text-primary-light" : "text-foreground-muted hover:text-foreground"
                }`}
              >
                Par numéro
              </button>
              <button
                onClick={() => setViewMode("theme")}
                className={`rounded-lg px-3 py-1.5 transition ${
                  viewMode === "theme" ? "bg-primary/10 text-primary-light" : "text-foreground-muted hover:text-foreground"
                }`}
              >
                Par thématique
              </button>
            </div>
          )}
          {viewMode === "number" && (
            <>
              <div className="relative w-full sm:w-72">
                <Icon name="search" className="absolute left-3 top-1/2 -translate-y-1/2 text-foreground-muted" />
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Rechercher un article..."
                  className="w-full rounded-xl border border-outline-variant bg-surface py-2 pl-10 pr-3 text-sm text-foreground outline-none transition focus:border-primary"
                />
              </div>
              {!q.trim() && (
                <select
                  value={pageSize}
                  onChange={(e) => setPageSize(e.target.value as PageSizeOption)}
                  className="rounded-xl border border-outline-variant bg-surface px-3 py-2 text-sm text-foreground"
                >
                  {PAGE_SIZE_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt === "all" ? "Tous" : `${opt} / page`}
                    </option>
                  ))}
                </select>
              )}
            </>
          )}
        </div>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {viewMode === "theme" ? (
        selectedTheme ? (
          <div className="space-y-4">
            <button
              onClick={() => setSelectedTheme(null)}
              className="inline-flex items-center gap-1 text-sm text-foreground-muted hover:text-foreground"
            >
              <Icon name="arrow_back" className="text-base" />
              Toutes les thématiques
            </button>
            <h2 className="text-lg font-semibold text-foreground">{selectedTheme.name}</h2>
            {themeMagazinesLoading && <p className="text-sm text-foreground-muted">Chargement...</p>}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
              {themeMagazines.map((m) => (
                <MagazineCard key={m.id} magazine={m} />
              ))}
            </div>
            {!themeMagazinesLoading && themeMagazines.length === 0 && (
              <p className="py-8 text-center text-sm text-foreground-muted">Aucun magazine pour cette thématique.</p>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {themesLoading && <p className="text-sm text-foreground-muted">Chargement des thématiques...</p>}
            <div className="flex flex-wrap gap-2">
              {themes.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setSelectedTheme(t)}
                  className="rounded-xl border border-outline-variant bg-surface px-4 py-2 text-sm text-foreground transition hover:border-primary"
                >
                  {t.name}
                  <span className="ml-2 font-mono text-xs text-foreground-muted">{t.magazine_count}</span>
                </button>
              ))}
            </div>
            {!themesLoading && themes.length === 0 && (
              <p className="py-8 text-center text-sm text-foreground-muted">
                Aucune thématique générée pour le moment — elles sont créées automatiquement à l'indexation de chaque
                numéro.
              </p>
            )}
          </div>
        )
      ) : q.trim() ? (
        <div className="space-y-6">
          {searching && <p className="text-sm text-foreground-muted">Recherche...</p>}
          {!searching &&
            Array.from(
              searchResults?.reduce((map, article) => {
                const existing = map.get(article.magazine_id);
                if (existing) existing.articles.push(article);
                else
                  map.set(article.magazine_id, {
                    title: article.magazine_title,
                    issueNumber: article.magazine_issue_number,
                    articles: [article],
                  });
                return map;
              }, new Map<number, { title: string; issueNumber: string | null; articles: ArticleWithMagazine[] }>()) ??
                new Map()
            ).map(([magazineId, group]) => (
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
                        <span className="shrink-0 font-mono text-xs text-foreground-muted">p.{article.start_page}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          {!searching && searchResults?.length === 0 && (
            <p className="py-8 text-center text-sm text-foreground-muted">Aucun article trouvé.</p>
          )}
        </div>
      ) : (
        <div className="space-y-6">
          {loading && <p className="text-sm text-foreground-muted">Chargement...</p>}
          {groups.map(({ magazine, articles }) => (
            <div key={magazine.id} className="overflow-hidden rounded-xl border border-outline-variant">
              <div className="bg-surface-hover px-4 py-3">
                <Link href={`/viewer/${magazine.id}/1`} className="text-sm font-semibold text-foreground hover:text-primary-light">
                  {magazine.title}
                  {magazine.issue_number ? ` — ${magazine.issue_number}` : ""}
                </Link>
              </div>
              <ul className="divide-y divide-outline-variant">
                {articles.map((article) => (
                  <li key={article.id}>
                    <Link
                      href={`/viewer/${magazine.id}/${article.start_page}`}
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
                {articles.length === 0 && (
                  <li className="px-4 py-3 text-sm text-foreground-muted">Aucun sommaire pour ce numéro.</li>
                )}
              </ul>
            </div>
          ))}
          {!loading && groups.length === 0 && (
            <p className="py-8 text-center text-sm text-foreground-muted">Aucun magazine trouvé.</p>
          )}

          {pageSize !== "all" && totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-4">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="rounded-lg border border-outline-variant px-3 py-1.5 text-sm text-foreground disabled:opacity-40"
              >
                <Icon name="chevron_left" />
              </button>
              <span className="font-mono text-xs text-foreground-muted">
                Page {page + 1} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="rounded-lg border border-outline-variant px-3 py-1.5 text-sm text-foreground disabled:opacity-40"
              >
                <Icon name="chevron_right" />
              </button>
            </div>
          )}
        </div>
      )}
    </PageContainer>
  );
}
