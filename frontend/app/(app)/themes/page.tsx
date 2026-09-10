"use client";

import { useEffect, useState } from "react";
import { api, ApiError, redirectToLogin } from "@/lib/api";
import type { Magazine, MagazineTheme } from "@/lib/types";
import PageContainer from "@/components/layout/PageContainer";
import MagazineCard from "@/components/library/MagazineCard";
import Icon from "@/components/ui/Icon";

const PAR_PAGE = 100;

export default function ThemesPage() {
  const [themes, setThemes] = useState<MagazineTheme[]>([]);
  const [selected, setSelected] = useState<MagazineTheme | null>(null);
  const [magazines, setMagazines] = useState<Magazine[]>([]);
  const [loadingThemes, setLoadingThemes] = useState(true);
  const [loadingMagazines, setLoadingMagazines] = useState(false);
  const [page, setPage] = useState(0);
  const [encoreDesNumeros, setEncoreDesNumeros] = useState(false);

  useEffect(() => {
    api
      .get<MagazineTheme[]>("/themes")
      .then(setThemes)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) redirectToLogin();
      })
      .finally(() => setLoadingThemes(false));
  }, []);

  // The server already orders themes by occurrence then recency, so the list
  // is rendered as received - re-sorting here would silently diverge from it.
  useEffect(() => {
    if (!selected) {
      setMagazines([]);
      setEncoreDesNumeros(false);
      return;
    }
    let annule = false;
    setLoadingMagazines(true);
    // The endpoint caps a response at 100 rows, and a well-represented theme
    // holds more than that, so pages are appended rather than replaced.
    api
      .get<Magazine[]>(`/magazines?theme_id=${selected.id}&page=${page}&limit=${PAR_PAGE}`)
      .then((data) => {
        if (annule) return;
        setMagazines((precedents) => (page === 0 ? data : [...precedents, ...data]));
        setEncoreDesNumeros(data.length === PAR_PAGE);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) redirectToLogin();
      })
      .finally(() => {
        if (!annule) setLoadingMagazines(false);
      });
    // A slow response for a theme the user has already left must not overwrite
    // the current one: the flag drops it on unmount or re-selection.
    return () => {
      annule = true;
    };
  }, [selected, page]);

  function choisirTheme(theme: MagazineTheme | null) {
    // Resetting the page alongside the theme keeps the two in step; without it
    // a theme picked while on page 2 would open on its second page of results.
    setPage(0);
    setMagazines([]);
    setSelected(theme);
  }

  return (
    <PageContainer>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-foreground">Thématiques</h1>
        <p className="mt-1 text-sm text-foreground-muted">
          Les thématiques les plus présentes dans votre collection, toutes revues confondues.
        </p>
      </div>

      {!loadingThemes && themes.length === 0 && (
        <p className="text-sm text-foreground-muted">
          Aucune thématique pour le moment. Elles sont générées à l&apos;indexation, à partir du sommaire.
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
        <div className="space-y-1 lg:max-h-[calc(100vh-12rem)] lg:overflow-y-auto lg:pr-2">
          {themes.map((theme) => {
            const actif = selected?.id === theme.id;
            return (
              <button
                key={theme.id}
                type="button"
                onClick={() => choisirTheme(actif ? null : theme)}
                className={`flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition ${
                  actif
                    ? "bg-primary/10 text-primary-light"
                    : "text-foreground-muted hover:bg-surface-hover hover:text-foreground"
                }`}
              >
                <span className="min-w-0 truncate">{theme.name}</span>
                <span className="shrink-0 rounded-full bg-surface-hover px-2 py-0.5 font-mono text-xs text-foreground-muted">
                  {theme.magazine_count}
                </span>
              </button>
            );
          })}
        </div>

        <div>
          {!selected && themes.length > 0 && (
            <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-outline-variant py-16 text-foreground-muted">
              <Icon name="label" className="text-3xl" />
              <p className="text-sm">Choisissez une thématique pour voir les numéros concernés.</p>
            </div>
          )}

          {selected && (
            <>
              <div className="mb-4 flex items-baseline gap-2">
                <h2 className="text-lg font-semibold text-foreground">{selected.name}</h2>
                <span className="text-sm text-foreground-muted">
                  {selected.magazine_count} numéro{selected.magazine_count > 1 ? "s" : ""}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                {magazines.map((magazine) => (
                  <MagazineCard key={magazine.id} magazine={magazine} />
                ))}
              </div>

              {loadingMagazines && <p className="mt-4 text-sm text-foreground-muted">Chargement…</p>}

              {!loadingMagazines && encoreDesNumeros && (
                <button
                  type="button"
                  onClick={() => setPage((p) => p + 1)}
                  className="mt-6 w-full rounded-xl border border-outline-variant py-2.5 text-sm text-foreground-muted transition hover:bg-surface-hover hover:text-foreground"
                >
                  Afficher plus de numéros
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
