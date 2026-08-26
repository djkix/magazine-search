"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError, fileUrl } from "@/lib/api";
import type { Magazine, Page } from "@/lib/types";
import PdfViewer from "@/components/PdfViewer";

function matchedTerms(query: string): Set<string> {
  return new Set((query.match(/\w+/gu) ?? []).map((w) => w.toLowerCase()));
}

export default function ViewerPage() {
  const params = useParams<{ magazineId: string; pageNumber: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();

  const magazineId = Number(params.magazineId);
  const pageNumber = Number(params.pageNumber);
  const query = searchParams.get("q") ?? "";

  const [magazine, setMagazine] = useState<Magazine | null>(null);
  const [page, setPage] = useState<Page | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setError(null);
    setPage(null);
    Promise.all([
      api.get<Magazine>(`/magazines/${magazineId}`),
      api.get<Page>(`/magazines/${magazineId}/pages/${pageNumber}`),
    ])
      .then(([m, p]) => {
        setMagazine(m);
        setPage(p);
      })
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          window.location.href = "/login";
          return;
        }
        setError(err instanceof ApiError ? err.message : "Page introuvable");
      });
  }, [magazineId, pageNumber]);

  const highlightWords = useMemo(() => {
    if (!page?.words || !query) return [];
    const terms = matchedTerms(query);
    return page.words.filter((w) => terms.has(w.text.replace(/\W+/gu, "").toLowerCase()));
  }, [page, query]);

  function goToPage(target: number) {
    if (target < 1) return;
    router.push(`/viewer/${magazineId}/${target}?q=${encodeURIComponent(query)}`);
  }

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!magazine || !page) return <p className="text-sm text-slate-500">Chargement...</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">{magazine.title}</h1>
          <p className="text-sm text-slate-500">
            Page {page.page_number} / {magazine.page_count}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <button
            onClick={() => goToPage(pageNumber - 1)}
            disabled={pageNumber <= 1}
            className="rounded border px-3 py-1.5 hover:bg-slate-100 disabled:opacity-40"
          >
            ← Précédente
          </button>
          <button
            onClick={() => goToPage(pageNumber + 1)}
            disabled={pageNumber >= magazine.page_count}
            className="rounded border px-3 py-1.5 hover:bg-slate-100 disabled:opacity-40"
          >
            Suivante →
          </button>
          <a
            href={fileUrl(`/magazines/${magazineId}/download`)}
            className="rounded border px-3 py-1.5 hover:bg-slate-100"
          >
            Télécharger
          </a>
          <Link href="/" className="rounded border px-3 py-1.5 hover:bg-slate-100">
            Retour
          </Link>
        </div>
      </div>

      <PdfViewer
        fileUrl={fileUrl(`/magazines/${magazineId}/file`)}
        pageNumber={pageNumber}
        highlightWords={highlightWords}
      />
    </div>
  );
}
