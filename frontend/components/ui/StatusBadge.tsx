import type { Magazine } from "@/lib/types";

type Status = Magazine["scan_status"];

const STATUS_STYLES: Record<Status, string> = {
  detected: "bg-foreground-muted/10 text-foreground-muted",
  stable: "bg-foreground-muted/10 text-foreground-muted",
  queued: "bg-primary-light/10 text-primary-light",
  processing: "bg-primary/10 text-primary-light",
  done: "bg-emerald-500/10 text-emerald-400",
  failed: "bg-red-500/10 text-red-400",
};

const STATUS_LABELS: Record<Status, string> = {
  detected: "Détecté",
  stable: "Stable",
  queued: "En file",
  processing: "OCR en cours",
  done: "Indexé",
  failed: "Échec",
};

export default function StatusBadge({ status }: { status: Status }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider ${
        STATUS_STYLES[status]
      } ${status === "processing" ? "animate-pulse" : ""}`}
    >
      {STATUS_LABELS[status]}
    </span>
  );
}
