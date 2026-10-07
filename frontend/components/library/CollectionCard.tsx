import Link from "next/link";
import { fileUrl } from "@/lib/api";
import Icon from "@/components/ui/Icon";
import ShareButton from "@/components/articles/ShareButton";

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
    <div className="group">
      <Link href={href} className="block">
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
        <p className="mt-2 truncate font-serif text-sm font-semibold text-foreground">{name}</p>
      </Link>
      <div className="flex items-center justify-between gap-2">
        <Link
          href={href}
          className="min-w-0 flex-1 truncate font-mono text-[10px] uppercase tracking-wider text-foreground-muted"
        >
          {count} {countLabel}
          {count !== 1 ? "s" : ""}
        </Link>
        {coverMagazineId && (
          <ShareButton kind="magazine" id={coverMagazineId} className="block shrink-0 lg:hidden lg:group-hover:block" />
        )}
      </div>
    </div>
  );
}
