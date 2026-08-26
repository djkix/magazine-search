import Link from "next/link";
import type { SearchHit } from "@/lib/types";
import { sanitizeHighlightedSnippet } from "@/lib/sanitize";

export default function ResultCard({ hit, query }: { hit: SearchHit; query: string }) {
  return (
    <Link
      href={`/viewer/${hit.magazine_id}/${hit.page_number}?q=${encodeURIComponent(query)}`}
      className="block rounded-lg border bg-white p-4 transition hover:border-slate-400 hover:shadow-sm"
    >
      <div className="mb-1 flex items-center justify-between text-sm text-slate-500">
        <span className="font-medium text-slate-700">{hit.magazine_title}</span>
        <span>page {hit.page_number}</span>
      </div>
      <p
        className="text-sm text-slate-700"
        dangerouslySetInnerHTML={{ __html: sanitizeHighlightedSnippet(hit.snippet) }}
      />
    </Link>
  );
}
