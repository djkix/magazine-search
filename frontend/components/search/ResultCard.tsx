import Link from "next/link";
import Icon from "@/components/ui/Icon";
import type { SearchHit } from "@/lib/types";
import { sanitizeHighlightedSnippet } from "@/lib/sanitize";
import { occurrenceColorRgb } from "@/lib/occurrenceColor";
import { formatYearMonth } from "@/lib/formatDate";

export default function ResultCard({
  hit,
  searchParamsString,
  maxOccurrence,
}: {
  hit: SearchHit;
  searchParamsString: string;
  maxOccurrence: number;
}) {
  const rgb = occurrenceColorRgb(hit.occurrence_count, maxOccurrence);
  const yearMonth = formatYearMonth(hit.publication_date);

  return (
    <Link
      href={`/viewer/${hit.magazine_id}/${hit.page_number}?${searchParamsString}`}
      className="block rounded-xl border border-outline-variant bg-surface/50 p-4 transition hover:border-primary hover:bg-surface"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-serif text-sm font-semibold text-foreground">{hit.magazine_title}</span>
        <span className="flex shrink-0 items-center gap-3 font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
          <span
            className="rounded-full px-2 py-0.5 font-semibold"
            style={{ color: `rgb(${rgb})`, backgroundColor: `rgba(${rgb}, 0.15)` }}
          >
            {hit.occurrence_count} occurrence{hit.occurrence_count > 1 ? "s" : ""}
          </span>
          <span className="flex items-center gap-1">
            <Icon name="description" className="text-sm" />
            Page {hit.page_number}
          </span>
        </span>
      </div>
      {(yearMonth || hit.issue_number) && (
        <p className="mb-2 flex items-center gap-3 font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
          {yearMonth && (
            <span className="flex items-center gap-1">
              <Icon name="calendar_today" className="text-xs" />
              {yearMonth}
            </span>
          )}
          {hit.issue_number && (
            <span className="flex items-center gap-1">
              <Icon name="tag" className="text-xs" />
              N° {hit.issue_number}
            </span>
          )}
        </p>
      )}
      <p
        className="text-sm leading-relaxed text-foreground-muted"
        dangerouslySetInnerHTML={{ __html: sanitizeHighlightedSnippet(hit.snippet) }}
      />
    </Link>
  );
}
