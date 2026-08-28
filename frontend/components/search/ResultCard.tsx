import Link from "next/link";
import Icon from "@/components/ui/Icon";
import type { SearchHit } from "@/lib/types";
import { sanitizeHighlightedSnippet } from "@/lib/sanitize";

// Endpoints of the occurrence-count color scale: low occurrence counts read
// as the app's neutral muted gray, high counts ramp toward its emerald
// "success" green, so the most relevant results visually pop the most.
const LOW = { r: 0x8b, g: 0xa0, b: 0xc2 }; // foreground-muted
const HIGH = { r: 0x34, g: 0xd3, b: 0x99 }; // emerald-400

function occurrenceColor(count: number, max: number): string {
  const t = max > 0 ? Math.min(count / max, 1) : 0;
  const r = Math.round(LOW.r + (HIGH.r - LOW.r) * t);
  const g = Math.round(LOW.g + (HIGH.g - LOW.g) * t);
  const b = Math.round(LOW.b + (HIGH.b - LOW.b) * t);
  return `${r}, ${g}, ${b}`;
}

export default function ResultCard({ hit, query, maxOccurrence }: { hit: SearchHit; query: string; maxOccurrence: number }) {
  const rgb = occurrenceColor(hit.occurrence_count, maxOccurrence);

  return (
    <Link
      href={`/viewer/${hit.magazine_id}/${hit.page_number}?q=${encodeURIComponent(query)}`}
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
      <p
        className="text-sm leading-relaxed text-foreground-muted"
        dangerouslySetInnerHTML={{ __html: sanitizeHighlightedSnippet(hit.snippet) }}
      />
    </Link>
  );
}
