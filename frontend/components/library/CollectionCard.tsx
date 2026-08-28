import Link from "next/link";
import { fileUrl } from "@/lib/api";
import Icon from "@/components/ui/Icon";

export default function CollectionCard({
  href,
  name,
  count,
  countLabel = "numéro",
  coverMagazineId,
}: {
  href: string;
  name: string;
  count: number;
  countLabel?: string;
  coverMagazineId: number | null;
}) {
  return (
    <Link href={href} className="group block">
      <div className="aspect-[3/4] w-full overflow-hidden rounded-lg border border-outline-variant bg-surface-hover">
        {coverMagazineId ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={fileUrl(`/magazines/${coverMagazineId}/cover`)}
            alt={name}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-foreground-muted">
            <Icon name="collections_bookmark" className="text-3xl" />
          </div>
        )}
      </div>
      <div className="mt-2 space-y-1">
        <p className="truncate font-serif text-sm font-semibold text-foreground">{name}</p>
        <p className="truncate font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
          {count} {countLabel}
          {count !== 1 ? "s" : ""}
        </p>
      </div>
    </Link>
  );
}
