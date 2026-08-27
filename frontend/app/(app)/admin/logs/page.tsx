"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { LogEntry, LogLevel } from "@/lib/types";
import Button from "@/components/ui/Button";
import Icon from "@/components/ui/Icon";

const LEVELS: LogLevel[] = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];

const LEVEL_STYLES: Record<LogLevel, string> = {
  DEBUG: "bg-foreground-muted/10 text-foreground-muted",
  INFO: "bg-primary/10 text-primary-light",
  WARNING: "bg-amber-500/10 text-amber-400",
  ERROR: "bg-red-500/10 text-red-400",
  CRITICAL: "bg-red-500/20 text-red-400",
};

export default function AdminLogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [level, setLevel] = useState<string>("");
  const [component, setComponent] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function loadLogs() {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ limit: "200" });
    if (level) params.set("level", level);
    if (component) params.set("component", component);
    api
      .get<LogEntry[]>(`/admin/logs?${params.toString()}`)
      .then(setLogs)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur"))
      .finally(() => setLoading(false));
  }

  useEffect(loadLogs, [level, component]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-xl font-semibold text-foreground">Logs</h1>
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            className="rounded-lg border border-outline-variant bg-surface px-3 py-2 text-sm text-foreground"
          >
            <option value="">Tous les niveaux</option>
            {LEVELS.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </select>
          <select
            value={component}
            onChange={(e) => setComponent(e.target.value)}
            className="rounded-lg border border-outline-variant bg-surface px-3 py-2 text-sm text-foreground"
          >
            <option value="">Tous les composants</option>
            <option value="backend">Backend</option>
            <option value="worker">Worker</option>
          </select>
          <Button onClick={loadLogs} disabled={loading} variant="secondary">
            <Icon name="refresh" className={loading ? "animate-spin" : ""} />
            Actualiser
          </Button>
        </div>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="overflow-hidden rounded-xl border border-outline-variant">
        <table className="w-full text-sm">
          <thead className="bg-surface-hover text-left font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
            <tr>
              <th className="px-4 py-3">Horodatage</th>
              <th className="px-4 py-3">Niveau</th>
              <th className="px-4 py-3">Composant</th>
              <th className="px-4 py-3">Logger</th>
              <th className="px-4 py-3">Message</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant">
            {logs.map((entry, i) => (
              <tr key={i} className="bg-surface/40 align-top">
                <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-foreground-muted">
                  {entry.timestamp}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider ${LEVEL_STYLES[entry.level] ?? LEVEL_STYLES.INFO}`}
                  >
                    {entry.level}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-foreground-muted">{entry.component}</td>
                <td className="px-4 py-3 font-mono text-xs text-foreground-muted">{entry.logger}</td>
                <td className="whitespace-pre-wrap break-words px-4 py-3 text-foreground">{entry.message}</td>
              </tr>
            ))}
            {!loading && logs.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-foreground-muted">
                  Aucun log pour ce filtre.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
