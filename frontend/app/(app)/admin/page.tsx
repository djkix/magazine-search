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
  const [error, setError] = useState<string | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function loadStats() {
    api
      .get<AdminStats>("/admin/stats")
      .then(setStats)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur"));
  }

  useEffect(loadStats, []);

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
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

  function poll(jobId: string) {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    const interval = setInterval(async () => {
      try {
        const status = await api.get<ScanStatusResponse>(`/admin/scan/${jobId}/status`);
        setScanJob(status);
        if (status.finished) {
          clearInterval(interval);
          pollIntervalRef.current = null;
          setScanning(false);
          loadStats();
        }
      } catch {
        clearInterval(interval);
        pollIntervalRef.current = null;
        setScanning(false);
      }
    }, 3000);
    pollIntervalRef.current = interval;
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-col items-start justify-between gap-4 rounded-xl border border-outline-variant bg-surface/60 p-6 backdrop-blur-sm sm:flex-row sm:items-center">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Tableau de bord</h1>
          <p className="mt-1 text-sm text-foreground-muted">
            Déclenchez un scan du NAS pour détecter et indexer de nouveaux numéros.
          </p>
        </div>
        <Button onClick={triggerScan} disabled={scanning}>
          <Icon name="sync" className={scanning ? "animate-spin" : ""} />
          {scanning ? "Scan en cours..." : "Scanner le NAS"}
        </Button>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {scanJob && (
        <div className="rounded-xl border border-outline-variant bg-surface/60 p-4 font-mono text-xs uppercase tracking-wider text-foreground-muted">
          Job {scanJob.job_id.slice(0, 8)} — détectés {scanJob.detected} · en cours {scanJob.processing} · terminés{" "}
          {scanJob.done} · échecs {scanJob.failed}
          {scanJob.finished ? " · terminé" : ""}
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
                  </td>
                </tr>
              ))}
              {stats && stats.recent.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-foreground-muted">
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
