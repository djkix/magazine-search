import Link from "next/link";
import Icon from "@/components/ui/Icon";
import type { SearchHit } from "@/lib/types";
import { sanitizeHighlightedSnippet } from "@/lib/sanitize";

export default function ResultCard({ hit, query }: { hit: SearchHit; query: string }) {
  return (
    <Link
      href={`/viewer/${hit.magazine_id}/${hit.page_number}?q=${encodeURIComponent(query)}`}
      className="block rounded-xl border border-outline-variant bg-surface/50 p-4 transition hover:border-primary hover:bg-surface"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-serif text-sm font-semibold text-foreground">{hit.magazine_title}</span>
        <span className="flex shrink-0 items-center gap-3 font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-primary-light">
            {hit.occurrence_count} occurrence{hit.occurrence_count > 1 ? "s" : ""}
          </span>
          <span className="flex items-center gap-1">
            <Icon name="description" className="text-sm" />
            Page {hit.page_number}
          </span>
        </span>
      </div>
      <p
        className="text-sm leading-relaxed text-foreground-muted"
        dangerouslySetInnerHTML={{ __html: sanitizeHighlightedSnippet(hit.snippet) }}
      />
    </Link>
  );
}
