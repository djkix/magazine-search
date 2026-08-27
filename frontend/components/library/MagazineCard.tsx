import Link from "next/link";
import { fileUrl } from "@/lib/api";
import type { Magazine } from "@/lib/types";
import Icon from "@/components/ui/Icon";

export default function MagazineCard({ magazine }: { magazine: Magazine }) {
  const canOpen = magazine.scan_status === "done" && magazine.page_count > 0;
  const meta = [magazine.issue_number, magazine.publication_date ? new Date(magazine.publication_date).getFullYear() : null]
    .filter(Boolean)
    .join(" · ");

  const content = (
    <>
      <div className="aspect-[3/4] w-full overflow-hidden rounded-lg border border-outline-variant bg-surface-hover">
        {magazine.cover_thumbnail_path ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={fileUrl(`/magazines/${magazine.id}/cover`)}
            alt={magazine.title}
            className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-foreground-muted">
            <Icon name="description" className="text-3xl" />
          </div>
        )}
      </div>
      <div className="mt-2 space-y-1">
        <p className="truncate font-serif text-sm font-semibold text-foreground">{magazine.title}</p>
        {meta && <p className="truncate font-mono text-[10px] uppercase tracking-wider text-foreground-muted">{meta}</p>}
        {magazine.collection_name && (
          <p className="truncate font-mono text-[10px] uppercase tracking-wider text-primary-light">
            {magazine.collection_name}
          </p>
        )}
      </div>
    </>
  );

  if (!canOpen) {
    return <div className="group cursor-not-allowed opacity-70">{content}</div>;
  }

  return (
    <Link href={`/viewer/${magazine.id}/1`} className="group block">
      {content}
    </Link>
  );
}
