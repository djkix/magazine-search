"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { AdminStats, RetryFailedResponse, ScanStatusResponse, ScanTriggerResponse } from "@/lib/types";
import StatCard from "@/components/admin/StatCard";
import StatusBadge from "@/components/ui/StatusBadge";
import Icon from "@/components/ui/Icon";
import Button from "@/components/ui/Button";

export default function AdminDashboardPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [scanJob, setScanJob] = useState<ScanStatusResponse | null>(null);
  const [scanning, setScanning] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [reprocessingId, setReprocessingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const scanJobTotal = scanJob ? scanJob.detected + scanJob.processing + scanJob.done + scanJob.failed : 0;
  const scanJobDone = scanJob ? scanJob.done + scanJob.failed : 0;

  function loadStats() {
    api
      .get<AdminStats>("/admin/stats")
      .then(setStats)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur"));
  }

  useEffect(loadStats, []);

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
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur lors de la relance");
    } finally {
      setReprocessingId(null);
    }
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

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon="library_books" label="Total PDF" value={stats?.total} />
        <StatCard icon="task_alt" label="OCR terminés" value={stats?.done} accent="text-emerald-400" />
        <StatCard icon="autorenew" label="En cours" value={stats?.processing} accent="text-primary-light" />
        <StatCard icon="error" label="Échecs" value={stats?.failed} accent="text-red-400" />
      </div>

      {!!stats?.failed && (
        <Button onClick={retryFailed} disabled={retrying} variant="secondary" className="w-fit">
          <Icon name="replay" className={retrying ? "animate-spin" : ""} />
          {retrying ? "Relance en cours..." : `Réessayer les ${stats.failed} échec(s)`}
        </Button>
      )}

      <div>
        <h2 className="mb-3 text-lg font-semibold text-foreground">Activité récente</h2>
        <div className="overflow-hidden rounded-xl border border-outline-variant">
          <table className="w-full text-sm">
            <thead className="bg-surface-hover text-left font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
              <tr>
                <th className="px-4 py-3">Titre</th>
                <th className="px-4 py-3">Ajouté le</th>
                <th className="px-4 py-3">Statut</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {stats?.recent.map((m) => (
                <tr key={m.id} className="bg-surface/40">
                  <td className="px-4 py-3 text-foreground">{m.title}</td>
                  <td className="px-4 py-3 font-mono text-xs text-foreground-muted">
                    {new Date(m.created_at).toLocaleDateString("fr-FR")}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={m.scan_status} />
                    {m.scan_status === "failed" && m.error_message && (
                      <p
                        className="mt-1 max-w-md truncate font-mono text-[10px] text-red-400"
                        title={m.error_message}
                      >
                        {m.error_message.split("Traceback")[0].trim()}
                      </p>
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
              {stats && stats.recent.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-foreground-muted">
                    Aucun scan effectué pour le moment.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
