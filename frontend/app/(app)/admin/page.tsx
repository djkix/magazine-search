"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, ApiError, fileUrl } from "@/lib/api";
import type {
  AdminStats,
  Magazine,
  Orphans,
  RetryFailedResponse,
  ScanStatusResponse,
  ScanTriggerResponse,
  SubthemeImportReport,
  CorpusExport,
} from "@/lib/types";
import StatCard from "@/components/admin/StatCard";
import StatusBadge from "@/components/ui/StatusBadge";
import Icon from "@/components/ui/Icon";
import Button from "@/components/ui/Button";

type StatusFilter = "done" | "processing" | "failed" | "pending" | "no_sommaire" | null;

const STATUS_FILTER_LABEL: Record<Exclude<StatusFilter, null>, string> = {
  done: "OCR terminés",
  processing: "En cours",
  failed: "Échecs",
  pending: "En file d'attente",
  no_sommaire: "Sans sommaire",
};

// "pending" spans three raw scan statuses (detected/stable/queued) - not a
// single value, so it's expressed as repeated scan_status params instead
// of the ScanStatus enum the other filters use directly.
const PENDING_SCAN_STATUSES = "scan_status=detected&scan_status=stable&scan_status=queued";

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [scanJob, setScanJob] = useState<ScanStatusResponse | null>(null);
  const [scanning, setScanning] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [reprocessingId, setReprocessingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [statusFilter, setStatusFilter] = useState<StatusFilter>(null);
  const statusFilterRef = useRef<StatusFilter>(null);
  const [filteredMagazines, setFilteredMagazines] = useState<Magazine[] | null>(null);
  const [filterLoading, setFilterLoading] = useState(false);
  const [filteredTotal, setFilteredTotal] = useState<number | null>(null);
  const [loadingMoreFiltered, setLoadingMoreFiltered] = useState(false);
  const [noSommaireCount, setNoSommaireCount] = useState<number | null>(null);
  const [reprocessingAllNoSommaire, setReprocessingAllNoSommaire] = useState(false);
  const [reocrAllNoSommaireRunning, setReocrAllNoSommaire] = useState(false);
  const [progressById, setProgressById] = useState<Record<number, { current: number; total: number }>>({});
  const [deduplicatingArticles, setDeduplicatingArticles] = useState(false);
  const [dedupeMessage, setDedupeMessage] = useState<string | null>(null);
  const [corpus, setCorpus] = useState<CorpusExport | null>(null);
  const [orphans, setOrphans] = useState<Orphans | null>(null);
  const [orphansOuverts, setOrphansOuverts] = useState(false);
  // Le fichier est conservé après la simulation : appliquer, c'est le
  // renvoyer tel quel avec le drapeau d'écriture, sans redemander à l'utilisateur
  // de le sélectionner une seconde fois.
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importReport, setImportReport] = useState<SubthemeImportReport | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importRunning, setImportRunning] = useState(false);

  const FILTER_PAGE_SIZE = 100;

  async function refreshProgress(magazines: Magazine[]) {
    const processingIds = magazines.filter((m) => m.scan_status === "processing").map((m) => m.id);
    if (processingIds.length === 0) return;
    const entries = await Promise.all(
      processingIds.map((id) =>
        api
          .get<{ current: number; total: number } | null>(`/admin/magazines/${id}/progress`)
          .then((p): [number, { current: number; total: number } | null] => [id, p])
          .catch((): [number, { current: number; total: number } | null] => [id, null])
      )
    );
    setProgressById((prev) => {
      const next = { ...prev };
      for (const [id, p] of entries) {
        if (p) next[id] = p;
        else delete next[id];
      }
      return next;
    });
  }

  function filterScanStatusParam(filter: StatusFilter) {
    if (filter === "pending") return PENDING_SCAN_STATUSES;
    if (filter === "no_sommaire") return "scan_status=done&has_sommaire=false";
    return `scan_status=${filter}`;
  }

  function filterQueryString(filter: StatusFilter, pageIndex: number) {
    return `${filterScanStatusParam(filter)}&sort=updated&page=${pageIndex}&limit=${FILTER_PAGE_SIZE}`;
  }

  function filterCountQueryString(filter: StatusFilter) {
    return filterScanStatusParam(filter);
  }

  const scanJobTotal = scanJob ? scanJob.detected + scanJob.processing + scanJob.done + scanJob.failed : 0;
  const scanJobDone = scanJob ? scanJob.done + scanJob.failed : 0;

  function loadStats() {
    api
      .get<AdminStats>("/admin/stats")
      .then((data) => {
        setStats(data);
        refreshProgress(data.recent);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur"));
    api
      .get<{ total: number }>("/magazines/count?scan_status=done&has_sommaire=false")
      .then((data) => setNoSommaireCount(data.total))
      .catch(() => setNoSommaireCount(null));
  }

  // The stat cards only ever reflected whatever loadStats() last fetched -
  // with no periodic refresh, they'd silently go stale while the worker
  // kept progressing through the queue in the background, showing e.g.
  // "0 en cours" even while a filtered view (fetched fresh on click)
  // showed a magazine actively processing. Refreshed here every 5s,
  // reading the live filter via a ref so the interval (set up once) never
  // acts on a stale closure of statusFilter.
  useEffect(() => {
    statusFilterRef.current = statusFilter;
  }, [statusFilter]);

  function refreshFilteredFirstPage() {
    const filter = statusFilterRef.current;
    if (!filter) return;
    Promise.all([
      api.get<Magazine[]>(`/magazines?${filterQueryString(filter, 0)}`),
      api.get<{ total: number }>(`/magazines/count?${filterCountQueryString(filter)}`),
    ])
      .then(([mags, countRes]) => {
        setFilteredMagazines(mags);
        setFilteredTotal(countRes.total);
        refreshProgress(mags);
      })
      .catch(() => {});
  }

  useEffect(() => {
    loadStats();
    const interval = setInterval(() => {
      loadStats();
      refreshFilteredFirstPage();
    }, 5000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Chargé une seule fois, volontairement hors du rafraîchissement à 5 s :
  // l'inventaire compte les titres distincts de toute la bibliothèque, et
  // n'évolue qu'après une réindexation.
  useEffect(() => {
    api
      .get<CorpusExport>("/admin/themes/export")
      .then(setCorpus)
      .catch(() => setCorpus(null));
  }, []);

  useEffect(() => {
    if (!statusFilter) {
      setFilteredMagazines(null);
      setFilteredTotal(null);
      return;
    }
    setFilterLoading(true);
    Promise.all([
      api.get<Magazine[]>(`/magazines?${filterQueryString(statusFilter, 0)}`),
      api.get<{ total: number }>(`/magazines/count?${filterCountQueryString(statusFilter)}`),
    ])
      .then(([mags, countRes]) => {
        setFilteredMagazines(mags);
        setFilteredTotal(countRes.total);
        refreshProgress(mags);
      })
      .catch((err) => {
        setFilteredMagazines([]);
        setFilteredTotal(null);
        setError(err instanceof ApiError ? err.message : "Erreur lors du chargement des magazines filtrés");
      })
      .finally(() => setFilterLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  async function loadMoreFiltered() {
    if (!filteredMagazines) return;
    setLoadingMoreFiltered(true);
    try {
      const nextPage = Math.floor(filteredMagazines.length / FILTER_PAGE_SIZE);
      const more = await api.get<Magazine[]>(`/magazines?${filterQueryString(statusFilter, nextPage)}`);
      setFilteredMagazines((prev) => [...(prev ?? []), ...more]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur lors du chargement des magazines filtrés");
    } finally {
      setLoadingMoreFiltered(false);
    }
  }

  useEffect(() => {
    api
      .get<{ job_id: string | null }>("/admin/scan/current")
      .then((data) => {
        if (data.job_id) {
          setScanning(true);
          poll(data.job_id);
        }
      })
      .catch(() => {});
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function triggerScan() {
    setScanning(true);
    setError(null);
    try {
      const trigger = await api.post<ScanTriggerResponse>("/admin/scan");
      poll(trigger.job_id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur de scan");
      setScanning(false);
    }
  }

  async function retryFailed() {
    setRetrying(true);
    setError(null);
    try {
      await api.post<RetryFailedResponse>("/admin/scan/retry-failed");
      loadStats();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur lors de la relance");
    } finally {
      setRetrying(false);
    }
  }

  async function reprocessMagazine(magazineId: number) {
    setReprocessingId(magazineId);
    setError(null);
    try {
      await api.post(`/admin/magazines/${magazineId}/reprocess`);
      loadStats();
      if (statusFilter) {
        setFilteredMagazines((prev) => prev?.filter((m) => m.id !== magazineId) ?? null);
        setFilteredTotal((prev) => (prev !== null ? Math.max(0, prev - 1) : prev));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur lors de la relance");
    } finally {
      setReprocessingId(null);
    }
  }

  // Rejoue uniquement l'extraction du sommaire, a partir du texte OCR deja
  // en base : quelques minutes pour toute la bibliotheque. C'est l'action
  // attendue apres une amelioration du parseur.
  async function reprocessAllNoSommaire() {
    setReprocessingAllNoSommaire(true);
    setError(null);
    try {
      await api.post<{ reprocessed: number }>("/admin/magazines/reprocess-no-sommaire");
      loadStats();
      if (statusFilter === "no_sommaire") {
        setFilteredMagazines([]);
        setFilteredTotal(0);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur lors de la relance");
    } finally {
      setReprocessingAllNoSommaire(false);
    }
  }

  // Relance le traitement COMPLET, OCR compris : environ une minute par
  // numero. Confirmation explicite, la difference de cout avec l'action
  // ci-dessus se compte en heures.
  async function reocrAllNoSommaire() {
    if (
      !window.confirm(
        `Relancer l'OCR complet de ${noSommaireCount} magazine(s) ?\n\n` +
          "Comptez environ une minute par numero, soit plusieurs heures.\n" +
          "N'est utile que si la logique OCR elle-meme a change : pour une " +
          "simple amelioration du parseur de sommaire, utilisez « Reextraire " +
          "les sommaires », qui prend quelques minutes."
      )
    ) {
      return;
    }
    setReocrAllNoSommaire(true);
    setError(null);
    try {
      await api.post<{ reprocessed: number }>("/admin/magazines/reocr-no-sommaire");
      loadStats();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur lors de la relance");
    } finally {
      setReocrAllNoSommaire(false);
    }
  }

  async function deduplicateArticles() {
    setDeduplicatingArticles(true);
    setDedupeMessage(null);
    setError(null);
    try {
      const result = await api.post<{ deleted: number }>("/admin/articles/deduplicate?dry_run=false");
      setDedupeMessage(
        result.deleted > 0 ? `${result.deleted} article(s) en double supprimé(s).` : "Aucun doublon trouvé."
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur lors de la suppression des doublons");
    } finally {
      setDeduplicatingArticles(false);
    }
  }

  // Un seul chemin pour la simulation et pour l'écriture : c'est le même
  // appel, au drapeau près. Deux fonctions distinctes auraient pu diverger,
  // et l'aperçu ne refléterait plus ce qui sera réellement écrit.
  // Chargé à la demande, pas au montage : le calcul parcourt tous les articles
  // de la bibliothèque et compte les mots de chaque titre orphelin. Inutile de
  // l'imposer à chaque ouverture du tableau de bord.
  async function basculerOrphans() {
    const ouvrir = !orphansOuverts;
    setOrphansOuverts(ouvrir);
    if (!ouvrir || orphans) return;
    try {
      setOrphans(await api.get<Orphans>("/admin/themes/subthemes/orphans"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur");
      setOrphansOuverts(false);
    }
  }

  async function envoyerImport(fichier: File, appliquer: boolean) {
    setImportRunning(true);
    setImportError(null);
    try {
      const form = new FormData();
      form.append("fichier", fichier);
      const rapport = await api.postForm<SubthemeImportReport>(
        `/admin/themes/import?appliquer=${appliquer}`,
        form
      );
      setImportReport(rapport);
      if (appliquer) setImportFile(null);
    } catch (err) {
      setImportReport(null);
      setImportError(err instanceof ApiError ? err.message : "Import impossible");
    } finally {
      setImportRunning(false);
    }
  }

  function toggleStatusFilter(status: Exclude<StatusFilter, null>) {
    setStatusFilter((prev) => (prev === status ? null : status));
  }

  function poll(jobId: string) {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    async function check() {
      try {
        const status = await api.get<ScanStatusResponse>(`/admin/scan/${jobId}/status`);
        setScanJob(status);
        if (status.finished) {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
          setScanning(false);
          loadStats();
        }
      } catch {
        if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
        setScanning(false);
      }
    }

    check();
    pollIntervalRef.current = setInterval(check, 3000);
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col items-start justify-between gap-4 rounded-xl border border-outline-variant bg-surface/60 p-6 backdrop-blur-sm sm:flex-row sm:items-center">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Tableau de bord</h1>
          <p className="mt-1 text-sm text-foreground-muted">
            Détecte et indexe les nouveaux numéros, et retrouve ceux qui ont été déplacés dans un autre répertoire.
          </p>
        </div>
        <Button onClick={triggerScan} disabled={scanning}>
          <Icon name="sync" className={scanning ? "animate-spin" : ""} />
          {scanning ? "Scan en cours..." : "Scan"}
        </Button>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {scanJob && (
        <div className="space-y-2 rounded-xl border border-outline-variant bg-surface/60 p-4">
          <div className="flex items-center justify-between font-mono text-xs uppercase tracking-wider text-foreground-muted">
            <span>Job {scanJob.job_id.slice(0, 8)}</span>
            <span>
              {scanJobTotal > 0 ? `${scanJobDone} / ${scanJobTotal}` : "—"}
              {scanJob.finished ? " · terminé" : ""}
            </span>
          </div>
          <div className="flex h-2 w-full overflow-hidden rounded-full bg-outline-variant/40">
            {scanJobTotal > 0 && (
              <>
                <div
                  className="h-full bg-emerald-400 transition-[width] duration-500"
                  style={{ width: `${(scanJob.done / scanJobTotal) * 100}%` }}
                />
                <div
                  className="h-full bg-primary transition-[width] duration-500"
                  style={{ width: `${(scanJob.processing / scanJobTotal) * 100}%` }}
                />
                <div
                  className="h-full bg-red-400 transition-[width] duration-500"
                  style={{ width: `${(scanJob.failed / scanJobTotal) * 100}%` }}
                />
              </>
            )}
          </div>
          <div className="flex gap-4 font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
            <span>détectés {scanJob.detected}</span>
            <span className="text-primary-light">en cours {scanJob.processing}</span>
            <span className="text-emerald-400">terminés {scanJob.done}</span>
            <span className="text-red-400">échecs {scanJob.failed}</span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <StatCard icon="library_books" label="Total PDF" value={stats?.total} onClick={() => setStatusFilter(null)} />
        <StatCard
          icon="task_alt"
          label="OCR terminés"
          value={stats?.done}
          accent="text-emerald-400"
          active={statusFilter === "done"}
          onClick={() => toggleStatusFilter("done")}
        />
        <StatCard
          icon="hourglass_empty"
          label="En file d'attente"
          value={stats?.pending}
          accent="text-foreground-muted"
          active={statusFilter === "pending"}
          onClick={() => toggleStatusFilter("pending")}
        />
        <StatCard
          icon="autorenew"
          label="En cours"
          value={stats?.processing}
          accent="text-primary-light"
          active={statusFilter === "processing"}
          onClick={() => toggleStatusFilter("processing")}
        />
        <StatCard
          icon="error"
          label="Échecs"
          value={stats?.failed}
          accent="text-red-400"
          active={statusFilter === "failed"}
          onClick={() => toggleStatusFilter("failed")}
        />
        <StatCard
          icon="menu_book"
          label="Sans sommaire"
          value={noSommaireCount ?? undefined}
          accent="text-orange-400"
          active={statusFilter === "no_sommaire"}
          onClick={() => toggleStatusFilter("no_sommaire")}
        />
        {/* Couverture de la taxonomie, comptee en ARTICLES et non en numeros :
            c'est le grain auquel les sous-thematiques sont rattachees. Pas de
            onClick, il n'existe pas de filtre correspondant dans la liste des
            magazines. */}
        <StatCard icon="label" label="Articles rattachés" value={stats?.articles_rattaches} />
        <StatCard
          icon="pending"
          label="Sans sous-thématique"
          value={stats ? stats.articles_total - stats.articles_rattaches : undefined}
          accent="text-orange-400"
        />
      </div>

      {!!noSommaireCount && (
        <div className="flex flex-col gap-2">
          <Button
            onClick={reprocessAllNoSommaire}
            disabled={reprocessingAllNoSommaire || reocrAllNoSommaireRunning}
            variant="secondary"
            className="w-fit"
          >
            <Icon name="replay" className={reprocessingAllNoSommaire ? "animate-spin" : ""} />
            {reprocessingAllNoSommaire
              ? "Réextraction en cours..."
              : `Réextraire les sommaires de ${noSommaireCount} magazine(s)`}
          </Button>
          <p className="text-xs text-foreground-muted">
            Relit le sommaire à partir du texte déjà extrait : quelques minutes, sans OCR ni
            appel Gemini. C&apos;est l&apos;action à utiliser après une amélioration du parseur.
          </p>

          <Button
            onClick={reocrAllNoSommaire}
            disabled={reprocessingAllNoSommaire || reocrAllNoSommaireRunning}
            variant="secondary"
            className="w-fit"
          >
            <Icon name="replay" className={reocrAllNoSommaireRunning ? "animate-spin" : ""} />
            {reocrAllNoSommaireRunning
              ? "Relance OCR en cours..."
              : `Relancer l'OCR complet (long)`}
          </Button>
          <p className="text-xs text-foreground-muted">
            Refait l&apos;OCR de zéro : environ une minute par numéro, soit plusieurs heures.
            Utile uniquement si la logique OCR elle-même a changé.
          </p>
        </div>
      )}

      {!!stats?.failed && (
        <Button onClick={retryFailed} disabled={retrying} variant="secondary" className="w-fit">
          <Icon name="replay" className={retrying ? "animate-spin" : ""} />
          {retrying ? "Relance en cours..." : `Réessayer les ${stats.failed} échec(s)`}
        </Button>
      )}

      <div className="flex items-center gap-3">
        <Button onClick={deduplicateArticles} disabled={deduplicatingArticles} variant="secondary" className="w-fit">
          <Icon name="content_copy" className={deduplicatingArticles ? "animate-spin" : ""} />
          {deduplicatingArticles ? "Nettoyage en cours..." : "Supprimer les articles en double"}
        </Button>
        {dedupeMessage && <p className="text-sm text-foreground-muted">{dedupeMessage}</p>}
      </div>

      <div className="space-y-3 rounded-xl border border-outline-variant bg-surface/60 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Sous-thématiques</h2>
            {/* Le parcours courant est celui des orphelins, plus bas : on
                n'enrichit que ce qui reste a classer. Cet export-ci rejoue
                TOUT depuis zero et ecrase la taxonomie existante — utile une
                seule fois, au demarrage. Le dire ici evite de telecharger 13
                500 titres en croyant faire un complement. */}
            <p className="mt-1 text-sm text-foreground-muted">
              Pour enrichir la taxonomie au quotidien, utilisez les{" "}
              <strong className="text-foreground">articles non rattachés</strong> ci-dessous.
            </p>
          </div>
          <a
            href={fileUrl("/admin/themes/export/file")}
            title="Corpus entier, pour reconstruire la taxonomie depuis zéro"
            className="shrink-0 rounded-xl border border-outline-variant px-3 py-2 text-xs text-foreground-muted transition hover:bg-surface-hover hover:text-foreground"
          >
            <Icon name="folder_zip" className="mr-1 align-middle text-base" />
            Corpus entier (repartir de zéro)
          </a>
        </div>

        {corpus === null && <p className="text-sm text-foreground-muted">Chargement…</p>}

        {corpus && (
          <p className="text-sm text-foreground-muted">
            <span className="font-mono text-foreground">{corpus.articles.toLocaleString("fr-FR")}</span>{" "}
            articles répartis sur{" "}
            <span className="font-mono text-foreground">{corpus.collections}</span> collections. Les
            collections sans article extrait sont omises.
          </p>
        )}

        <div className="border-t border-outline-variant pt-4">
          <button
            type="button"
            onClick={basculerOrphans}
            className="flex items-center gap-1 text-sm text-foreground-muted transition hover:text-foreground"
          >
            <Icon name={orphansOuverts ? "expand_less" : "expand_more"} className="text-base" />
            Articles non rattachés
          </button>

          {orphansOuverts && orphans === null && (
            <p className="mt-2 text-sm text-foreground-muted">Analyse du corpus…</p>
          )}

          {orphansOuverts && orphans && (
            <div className="mt-3 space-y-3">
              <p className="text-sm text-foreground-muted">
                <span className="font-mono text-foreground">
                  {orphans.articles_orphelins.toLocaleString("fr-FR")}
                </span>{" "}
                article(s) sur {orphans.articles_total.toLocaleString("fr-FR")} ne sont rattachés à
                aucune sous-thématique.
              </p>

              {/* Export distinct de celui du corpus complet : celui-ci ne
                  contient que les orphelins, accompagnés de la taxonomie déjà
                  en place. Le modèle l'ÉTEND au lieu de la reconstruire, et on
                  ne lui fait pas relire 13 500 titres déjà classés. */}
              {orphans.articles_orphelins > 0 && (
                <a
                  href={fileUrl("/admin/themes/orphans/export/file")}
                  className="inline-block rounded-xl border border-outline-variant px-3 py-2 text-sm text-foreground-muted transition hover:bg-surface-hover hover:text-foreground"
                >
                  <Icon name="download" className="mr-1 align-middle text-base" />
                  1. Télécharger <span className="font-mono">pour-l-IA.json</span>
                </a>
              )}

              {/* Le levier gratuit : un terme qui revient souvent ici et
                  qu'aucun mot-clé ne couvre se complète à la main, sans
                  repasser par un modèle. */}
              {orphans.mots_frequents.length > 0 && (
                <div>
                  <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
                    Mots les plus fréquents parmi eux
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {orphans.mots_frequents.map((m) => (
                      <span
                        key={m.mot}
                        className="rounded-full bg-surface-hover px-2.5 py-1 text-xs text-foreground"
                      >
                        {m.mot}{" "}
                        <span className="font-mono text-foreground-muted">{m.occurrences}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {orphans.exemples.length > 0 && (
                <div>
                  <p className="mb-1 font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
                    Exemples de titres
                  </p>
                  <ul className="space-y-0.5 text-xs text-foreground-muted">
                    {orphans.exemples.map((t, i) => (
                      <li key={i} className="truncate">
                        {t}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="space-y-3 border-t border-outline-variant pt-4">
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              2. Déposer <span className="font-mono">reponse-de-l-IA.json</span>
            </h3>
            <p className="mt-1 text-sm text-foreground-muted">
              Le fichier que l&apos;IA vous a rendu. Rien n&apos;est écrit tant que vous n&apos;avez pas
              confirmé.
            </p>
          </div>

          <input
            type="file"
            accept="application/json,.json"
            onChange={(e) => {
              const fichier = e.target.files?.[0] ?? null;
              setImportFile(fichier);
              setImportReport(null);
              setImportError(null);
              // La simulation part dès la sélection : l'utilisateur veut voir
              // le résultat, pas cliquer une fois de plus pour l'obtenir.
              if (fichier) envoyerImport(fichier, false);
            }}
            className="block w-full text-sm text-foreground-muted file:mr-3 file:rounded-lg file:border-0 file:bg-primary/10 file:px-3 file:py-2 file:text-sm file:text-primary-light hover:file:bg-primary/20"
          />

          {importRunning && <p className="text-sm text-foreground-muted">Analyse en cours…</p>}
          {importError && <p className="text-sm text-red-400">{importError}</p>}

          {importReport && (
            <div className="space-y-3 rounded-xl border border-outline-variant bg-surface/40 p-3">
              <p className="text-sm text-foreground">
                <span className="font-semibold">{importReport.thematiques}</span> thématique(s),{" "}
                <span className="font-semibold">{importReport.sous_thematiques.length}</span>{" "}
                sous-thématique(s)
              </p>

              <div className="max-h-96 overflow-auto rounded-lg border border-outline-variant">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-surface-hover text-left font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
                    <tr>
                      <th className="px-3 py-2">Thématique</th>
                      <th className="px-3 py-2">Sous-thématique</th>
                      <th className="px-3 py-2">Articles</th>
                      <th className="px-3 py-2">Mots-clés sans correspondance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant">
                    {importReport.sous_thematiques.map((st) => (
                      <tr key={`${st.thematique}/${st.nom}`} className="bg-surface/40">
                        <td className="px-3 py-2 text-foreground-muted">{st.thematique}</td>
                        <td className="px-3 py-2 text-foreground">{st.nom}</td>
                        <td className="px-3 py-2 font-mono text-xs text-foreground-muted">{st.articles}</td>
                        <td className="px-3 py-2 text-xs text-amber-400">
                          {st.mots_cles_steriles.length > 0 ? st.mots_cles_steriles.join(", ") : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <p className="font-mono text-xs text-foreground-muted">
                {importReport.articles_couverts} article(s) rattaché(s) sur{" "}
                {importReport.articles_corpus} · {importReport.articles_sans_sous_thematique} sans
                rattachement
              </p>

              {/* Un corpus couvert à moins de la moitié trahit des mots-clés trop
                  étroits : mieux vaut le signaler que de publier une navigation
                  dont la majorité des articles est absente. */}
              {importReport.articles_corpus > 0 &&
                importReport.articles_couverts < importReport.articles_corpus / 2 && (
                  <p className="text-sm text-amber-400">
                    Moins de la moitié du corpus est rattachée. Les mots-clés sont probablement trop
                    étroits, ou trop peu nombreux — vous pouvez compléter en déposant un second
                    fichier, l&apos;import s&apos;ajoute au précédent.
                  </p>
                )}

              {importReport.entrees_ignorees.length > 0 && (
                <p className="text-sm text-foreground-muted">
                  Entrées ignorées, nom ou mots-clés absents : {importReport.entrees_ignorees.join(", ")}
                </p>
              )}

              {importReport.applique ? (
                <p className="text-sm text-primary-light">Appliqué.</p>
              ) : (
                <Button
                  onClick={() => importFile && envoyerImport(importFile, true)}
                  disabled={importRunning || !importFile}
                >
                  Appliquer
                </Button>
              )}
            </div>
          )}
        </div>
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">
            {statusFilter ? `Filtré : ${STATUS_FILTER_LABEL[statusFilter]}` : "Activité récente"}
          </h2>
          {statusFilter && (
            <button
              onClick={() => setStatusFilter(null)}
              className="flex items-center gap-1 rounded-full bg-primary/20 px-3 py-1.5 text-xs text-primary-light"
            >
              Réinitialiser
              <Icon name="close" className="text-sm" />
            </button>
          )}
        </div>
        <div className="overflow-hidden rounded-xl border border-outline-variant">
          <table className="w-full text-sm">
            <thead className="bg-surface-hover text-left font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
              <tr>
                <th className="px-4 py-3">Titre</th>
                <th className="px-4 py-3">Dernière activité</th>
                <th className="px-4 py-3">Statut</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {filterLoading && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-foreground-muted">
                    Chargement...
                  </td>
                </tr>
              )}
              {!filterLoading &&
              (statusFilter ? filteredMagazines ?? [] : stats?.recent ?? []).map((m) => (
                <tr key={m.id} className="bg-surface/40">
                  <td className="px-4 py-3 text-foreground">
                    <Link
                      href={`/viewer/${m.id}/1`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-primary-light hover:underline"
                    >
                      {m.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-foreground-muted">
                    {new Date(m.updated_at).toLocaleString("fr-FR", {
                      day: "2-digit",
                      month: "2-digit",
                      year: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={m.scan_status} />
                    {m.scan_status === "processing" && progressById[m.id] && (
                      <div className="mt-1 flex items-center gap-1.5">
                        <div className="h-1 w-16 overflow-hidden rounded-full bg-outline-variant/40">
                          <div
                            className="h-full bg-primary transition-[width] duration-500"
                            style={{
                              width: `${Math.round((progressById[m.id].current / progressById[m.id].total) * 100)}%`,
                            }}
                          />
                        </div>
                        <span className="font-mono text-[10px] text-primary-light">
                          {Math.round((progressById[m.id].current / progressById[m.id].total) * 100)}%
                        </span>
                      </div>
                    )}
                    {m.scan_status === "failed" && m.error_message && (
                      <p
                        className="mt-1 max-w-md truncate font-mono text-[10px] text-red-400"
                        title={m.error_message}
                      >
                        {m.error_message.split("Traceback")[0].trim()}
                      </p>
                    )}
                    {statusFilter === "no_sommaire" && (
                      <p className="mt-1 font-mono text-[10px] text-orange-400">{m.article_count} article(s)</p>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => reprocessMagazine(m.id)}
                      disabled={reprocessingId === m.id}
                      className="text-xs text-primary-light hover:underline disabled:opacity-50"
                    >
                      {reprocessingId === m.id ? "Relance..." : "Relancer"}
                    </button>
                  </td>
                </tr>
              ))}
              {!filterLoading && (statusFilter ? filteredMagazines?.length === 0 : stats?.recent.length === 0) && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-foreground-muted">
                    {statusFilter ? "Aucun magazine avec ce statut." : "Aucun scan effectué pour le moment."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {statusFilter && filteredMagazines && filteredTotal !== null && filteredMagazines.length < filteredTotal && (
          <div className="mt-3 flex items-center justify-between">
            <p className="font-mono text-xs text-foreground-muted">
              Affichage de {filteredMagazines.length} sur {filteredTotal}
            </p>
            <button
              onClick={loadMoreFiltered}
              disabled={loadingMoreFiltered}
              className="rounded-lg border border-outline-variant px-3 py-1.5 text-xs text-foreground disabled:opacity-50"
            >
              {loadingMoreFiltered ? "Chargement..." : "Charger plus"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
