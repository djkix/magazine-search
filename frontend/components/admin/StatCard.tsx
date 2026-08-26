import Icon from "@/components/ui/Icon";

export default function StatCard({
  icon,
  label,
  value,
  accent = "text-foreground",
}: {
  icon: string;
  label: string;
  value?: number;
  accent?: string;
}) {
  return (
    <div className="rounded-xl border border-outline-variant bg-surface/60 p-5 backdrop-blur-sm">
      <Icon name={icon} className={`mb-3 text-2xl ${accent}`} />
      <p className={`font-serif text-2xl font-semibold ${accent}`}>{value ?? "—"}</p>
      <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-foreground-muted">{label}</p>
    </div>
  );
}
