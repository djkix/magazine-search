import Icon from "@/components/ui/Icon";

export default function StatCard({
  icon,
  label,
  value,
  accent = "text-foreground",
  active = false,
  onClick,
}: {
  icon: string;
  label: string;
  value?: number;
  accent?: string;
  active?: boolean;
  onClick?: () => void;
}) {
  if (!onClick) {
    return (
      <div className="flex w-full flex-col items-center rounded-xl border border-outline-variant bg-surface/60 p-5 text-center backdrop-blur-sm">
        <Icon name={icon} className={`mb-3 text-2xl ${accent}`} />
        <p className={`font-serif text-2xl font-semibold ${accent}`}>{value ?? "—"}</p>
        <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-foreground-muted">{label}</p>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex w-full flex-col items-center rounded-xl border p-5 text-center backdrop-blur-sm transition hover:border-primary ${
        active ? "border-primary bg-primary/5" : "border-outline-variant bg-surface/60"
      }`}
    >
      <Icon name={icon} className={`mb-3 text-2xl ${accent}`} />
      <p className={`font-serif text-2xl font-semibold ${accent}`}>{value ?? "—"}</p>
      <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-foreground-muted">{label}</p>
    </button>
  );
}
