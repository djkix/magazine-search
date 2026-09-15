"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError, redirectToLogin } from "@/lib/api";
import type {
  Subtheme,
  SubthemeArticle,
  SubthemeCollectionGroup,
  TaxonomyTheme,
} from "@/lib/types";
import PageContainer from "@/components/layout/PageContainer";
import Icon from "@/components/ui/Icon";

// Référence d'un article : « Avril 2019 · n°64 ».
//
// L'année vient de publication_date, issue_month_label ne portant que le mois
// (« Avril ») — sans elle, deux numéros d'avril à dix ans d'écart étaient
// indiscernables dans la liste.
//
// Chaque élément est facultatif : un numéro sans date ni numérotation retombe
// sur le titre du magazine plutôt que d'afficher une chaîne vide.
function reference(a: SubthemeArticle): string {
  const annee = a.publication_date ? new Date(a.publication_date).getFullYear() : null;
  const anneeValide = annee !== null && !Number.isNaN(annee);

  const periode = [a.issue_month_label, anneeValide ? String(annee) : null]
    .filter(Boolean)
    .join(" ");
  const numero = a.issue_number ? `n°${a.issue_number}` : null;

  return [periode || null, numero].filter(Boolean).join(" · ") || a.magazine_title;
}

export default function ThemesPage() {
  const [themes, setThemes] = useState<TaxonomyTheme[] | null>(null);
  const [theme, setTheme] = useState<TaxonomyTheme | null>(null);
  const [subthemes, setSubthemes] = useState<Subtheme[] | null>(null);
  const [subtheme, setSubtheme] = useState<Subtheme | null>(null);
  const [groupes, setGroupes] = useState<SubthemeCollectionGroup[] | null>(null);

  useEffect(() => {
    api
      .get<TaxonomyTheme[]>("/themes/taxonomie")
      .then(setThemes)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) redirectToLogin();
        setThemes([]);
      });
  }, []);

  // Une réponse lente pour une thématique déjà quittée ne doit pas écraser la
  // courante : le drapeau l'écarte au démontage comme à la re-sélection.
  useEffect(() => {
    if (!theme) {
      setSubthemes(null);
      return;
    }
    let annule = false;
    setSubthemes(null);
    api
      .get<Subtheme[]>(`/themes/${theme.id}/subthemes`)
      .then((d) => !annule && setSubthemes(d))
      .catch(() => !annule && setSubthemes([]));
    return () => {
      annule = true;
    };
  }, [theme]);

  useEffect(() => {
    if (!subtheme) {
      setGroupes(null);
      return;
    }
    let annule = false;
    setGroupes(null);
    api
      .get<SubthemeCollectionGroup[]>(`/themes/subthemes/${subtheme.id}/articles`)
      .then((d) => !annule && setGroupes(d))
      .catch(() => !annule && setGroupes([]));
    return () => {
      annule = true;
    };
  }, [subtheme]);

  function choisirTheme(t: TaxonomyTheme | null) {
    // Le niveau 3 se vide avec le niveau 1 : sans cela, les articles d'une
    // sous-thématique d'une autre thématique resteraient affichés.
    setSubtheme(null);
    setTheme(t);
  }

  return (
    <PageContainer>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-foreground">Thématiques</h1>
        <p className="mt-1 text-sm text-foreground-muted">
          Les sujets traités par vos magazines, article par article.
        </p>
      </div>

      {themes?.length === 0 && (
        <div className="rounded-xl border border-dashed border-outline-variant p-6 text-sm text-foreground-muted">
          <p>Aucune thématique n&apos;est encore rattachée.</p>
          <p className="mt-2">
            La taxonomie se construit hors ligne : téléchargez le corpus depuis{" "}
            <Link href="/admin" className="text-primary-light hover:underline">
              l&apos;administration
            </Link>
            , soumettez-le à un modèle de langage, puis réinjectez sa réponse.
          </p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
        <div className="space-y-1 lg:max-h-[calc(100vh-12rem)] lg:overflow-y-auto lg:pr-2">
          {themes === null && <p className="text-sm text-foreground-muted">Chargement…</p>}
          {themes?.map((t) => {
            const actif = theme?.id === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => choisirTheme(actif ? null : t)}
                className={`flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition ${
                  actif
                    ? "bg-primary/10 text-primary-light"
                    : "text-foreground-muted hover:bg-surface-hover hover:text-foreground"
                }`}
              >
                {/* Pas de `truncate` ici : une thématique de niveau 1 est un
                    repère de navigation, la couper la rend indevinable. Le
                    retour à la ligne garantit l'affichage complet quelle que
                    soit la longueur du libellé. */}
                <span className="min-w-0 break-words">{t.name}</span>
                <span className="shrink-0 rounded-full bg-surface-hover px-2 py-0.5 font-mono text-xs text-foreground-muted">
                  {t.article_count}
                </span>
              </button>
            );
          })}
        </div>

        <div>
          {!theme && themes && themes.length > 0 && (
            <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-outline-variant py-16 text-foreground-muted">
              <Icon name="label" className="text-3xl" />
              <p className="text-sm">Choisissez une thématique.</p>
            </div>
          )}

          {theme && !subtheme && (
            <>
              <h2 className="mb-3 text-lg font-semibold text-foreground">{theme.name}</h2>
              {subthemes === null && <p className="text-sm text-foreground-muted">Chargement…</p>}
              <div className="grid gap-2 sm:grid-cols-2">
                {subthemes?.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setSubtheme(s)}
                    disabled={s.article_count === 0}
                    className="flex items-center justify-between gap-3 rounded-xl border border-outline-variant bg-surface/50 px-3 py-2.5 text-left text-sm transition enabled:hover:border-primary disabled:opacity-40"
                    // Une sous-thématique à zéro article signale des mots-clés
                    // qui n'accrochent rien : on la montre — c'est une
                    // information — mais elle n'ouvre sur rien.
                    title={s.article_count === 0 ? "Aucun article rattaché" : undefined}
                  >
                    <span className="min-w-0 truncate text-foreground">{s.name}</span>
                    <span className="shrink-0 font-mono text-xs text-foreground-muted">
                      {s.article_count}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}

          {subtheme && (
            <>
              <button
                type="button"
                onClick={() => setSubtheme(null)}
                className="mb-3 flex items-center gap-1 text-sm text-foreground-muted transition hover:text-foreground"
              >
                <Icon name="arrow_back" className="text-base" />
                {theme?.name}
              </button>

              <h2 className="mb-4 text-lg font-semibold text-foreground">
                {subtheme.name}{" "}
                <span className="font-normal text-foreground-muted">
                  · {subtheme.article_count} article{subtheme.article_count > 1 ? "s" : ""}
                </span>
              </h2>

              {groupes === null && <p className="text-sm text-foreground-muted">Chargement…</p>}

              <div className="space-y-6">
                {groupes?.map((g) => (
                  <div key={g.collection_id ?? "sans-collection"}>
                    {/* « 212 » seul se lisait comme un nombre de numéros
                        alors que ce sont des articles : l'unité est écrite. */}
                    <div className="mb-2 flex items-baseline gap-2 border-l-2 border-primary pl-3">
                      <h3 className="font-serif text-base font-semibold text-foreground">
                        {g.collection_name}
                      </h3>
                      <span className="font-mono text-xs text-foreground-muted">
                        {g.article_count} article{g.article_count > 1 ? "s" : ""}
                      </span>
                    </div>
                    <div className="divide-y divide-outline-variant overflow-hidden rounded-xl border border-outline-variant">
                      {g.articles.map((a) => (
                        <Link
                          key={a.id}
                          href={`/viewer/${a.magazine_id}/${a.start_page}`}
                          className="flex items-baseline gap-3 bg-surface/40 px-4 py-2.5 text-sm transition hover:bg-surface-hover"
                        >
                          {/* Les titres viennent de l'OCR : ils sont longs et souvent
                              concatenes. Les couper sur une ligne les rendait illisibles ;
                              on les laisse passer a la ligne, plafonnes a deux lignes pour
                              que la liste reste parcourable. Le titre complet reste
                              accessible en infobulle. */}
                          <span
                            className="min-w-0 flex-1 line-clamp-2 [overflow-wrap:anywhere] text-foreground"
                            title={a.title}
                          >
                            {a.title}
                          </span>
                          <span className="shrink-0 truncate text-xs text-foreground-muted">
                            {reference(a)}
                          </span>
                          <span className="shrink-0 font-mono text-xs text-foreground-muted">
                            p.{a.start_page}
                          </span>
                        </Link>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
