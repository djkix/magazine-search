import Link from "next/link";
import { fileUrl } from "@/lib/api";
import type { Magazine } from "@/lib/types";
import Icon from "@/components/ui/Icon";

const ISSUE_TYPE_LABEL: Record<Magazine["issue_type"], string | null> = {
  normal: null,
  hs: "HS",
  sp: "SP",
};

export default function MagazineCard({
  magazine,
  onYearClick,
}: {
  magazine: Magazine;
  onYearClick?: (year: number) => void;
}) {
  const canOpen = magazine.scan_status === "done" && magazine.page_count > 0;
  const year = magazine.publication_date ? new Date(magazine.publication_date).getFullYear() : null;
  const issueTypeLabel = ISSUE_TYPE_LABEL[magazine.issue_type];

  const content = (
    <>
      <div className="relative aspect-[3/4] w-full overflow-hidden rounded-lg border border-outline-variant bg-surface-hover">
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
        {issueTypeLabel && (
          <span className="absolute right-1.5 top-1.5 rounded-full bg-primary px-2 py-0.5 font-mono text-[10px] font-semibold text-white">
            {issueTypeLabel}
          </span>
        )}
      </div>
      <div className="mt-2 space-y-1">
        <p className="truncate font-serif text-sm font-semibold text-foreground">{magazine.title}</p>
        <p className="flex items-center gap-1 truncate font-mono text-[10px] uppercase tracking-wider text-primary-light">
          {magazine.collection_name && <span className="truncate">{magazine.collection_name}</span>}
          {magazine.collection_name && year && <span>·</span>}
          {year &&
            (onYearClick ? (
              <button
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onYearClick(year);
                }}
                className="shrink-0 hover:underline"
              >
                {year}
              </button>
            ) : (
              <span className="shrink-0">{year}</span>
            ))}
        </p>
        {(magazine.issue_number || magazine.issue_month) && (
          <p className="truncate font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
            {[magazine.issue_number, magazine.issue_month].filter(Boolean).join(" · ")}
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
