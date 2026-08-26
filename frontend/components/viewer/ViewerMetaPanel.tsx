import type { Magazine } from "@/lib/types";

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

export default function ViewerMetaPanel({ magazine }: { magazine: Magazine }) {
  const rows = [
    { label: "Titre", value: magazine.title },
    { label: "Numéro", value: magazine.issue_number ?? "—" },
    {
      label: "Date de publication",
      value: magazine.publication_date ? new Date(magazine.publication_date).toLocaleDateString("fr-FR") : "—",
    },
    { label: "Fichier", value: magazine.filename },
    { label: "Taille", value: formatSize(magazine.file_size) },
    { label: "Pages", value: String(magazine.page_count) },
  ];

  return (
    <div className="space-y-4 p-4">
      <p className="font-mono text-xs uppercase tracking-wider text-foreground-muted">Métadonnées</p>
      <dl className="space-y-3">
        {rows.map((row) => (
          <div key={row.label}>
            <dt className="font-mono text-[10px] uppercase tracking-wider text-foreground-muted">{row.label}</dt>
            <dd className="mt-0.5 truncate text-sm text-foreground">{row.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
