"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { api, ApiError, fileUrl } from "@/lib/api";
import type { Magazine, SearchHit, WordBox } from "@/lib/types";
import PdfViewer from "@/components/viewer/PdfViewer";
import ViewerToolbar from "@/components/viewer/ViewerToolbar";
import ViewerSearchPanel from "@/components/viewer/ViewerSearchPanel";
import ViewerMetaPanel from "@/components/viewer/ViewerMetaPanel";
import ViewerMobileNav from "@/components/viewer/ViewerMobileNav";

export default function ViewerPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-foreground-muted">Chargement...</div>}>
      <ViewerContent />
    </Suspense>
  );
}

function ViewerContent() {
  const params = useParams<{ magazineId: string; pageNumber: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();

  const magazineId = Number(params.magazineId);
  const urlPageNumber = Number(params.pageNumber);
  const initialQuery = searchParams.get("q") ?? "";

  const [magazine, setMagazine] = useState<Magazine | null>(null);
  const [pageNumber, setPageNumber] = useState(urlPageNumber);
  const [pageCount, setPageCount] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);
  const [highlightWords, setHighlightWords] = useState<WordBox[]>([]);
  const [mobilePanel, setMobilePanel] = useState<"search" | "meta" | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Only the page number tracks the URL — highlights are managed explicitly by
  // goToPage() / handleSelectHit() so a hit click isn't wiped by this effect.
  useEffect(() => {
    setPageNumber(urlPageNumber);
  }, [urlPageNumber]);

  useEffect(() => {
    api
      .get<Magazine>(`/magazines/${magazineId}`)
      .then(setMagazine)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          window.location.href = "/login";
          return;
        }
        setError(err instanceof ApiError ? err.message : "Magazine introuvable");
      });
  }, [magazineId]);

  function goToPage(target: number) {
    if (!pageCount || target < 1 || target > pageCount) return;
    setHighlightWords([]);
    router.push(`/viewer/${magazineId}/${target}`);
  }

  const handleSelectHit = useCallback(
    (hit: SearchHit) => {
      setHighlightWords(hit.words);
      if (hit.page_number !== pageNumber) {
        router.push(`/viewer/${magazineId}/${hit.page_number}`);
      }
      setMobilePanel(null);
    },
    [magazineId, pageNumber, router]
  );

  if (error) return <div className="p-8 text-sm text-red-400">{error}</div>;
  if (!magazine) return <div className="p-8 text-sm text-foreground-muted">Chargement...</div>;

  const effectivePageCount = pageCount ?? magazine.page_count;

  return (
    <div className="flex h-screen flex-col">
      <ViewerToolbar
        title={magazine.title}
        pageNumber={pageNumber}
        pageCount={effectivePageCount}
        zoom={zoom}
        onZoomIn={() => setZoom((z) => Math.min(2.5, +(z + 0.25).toFixed(2)))}
        onZoomOut={() => setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))}
        onPrev={() => goToPage(pageNumber - 1)}
        onNext={() => goToPage(pageNumber + 1)}
        downloadHref={fileUrl(`/magazines/${magazineId}/download`)}
      />

      <div className="grid flex-1 overflow-hidden lg:grid-cols-[300px_1fr_300px]">
        <aside className="hidden overflow-y-auto border-r border-outline-variant bg-surface/40 lg:block">
          <ViewerSearchPanel
            magazineId={magazineId}
            initialQuery={initialQuery}
            currentPage={pageNumber}
            onSelectHit={handleSelectHit}
          />
        </aside>

        <div className="relative overflow-hidden bg-background">
          <PdfViewer
            fileUrl={fileUrl(`/magazines/${magazineId}/file`)}
            pageNumber={pageNumber}
            zoom={zoom}
            highlightWords={highlightWords}
            onPageCount={setPageCount}
          />
        </div>

        <aside className="hidden overflow-y-auto border-l border-outline-variant bg-surface/40 lg:block">
          <ViewerMetaPanel magazine={magazine} />
        </aside>
      </div>

      <ViewerMobileNav
        pageNumber={pageNumber}
        pageCount={effectivePageCount}
        onPrev={() => goToPage(pageNumber - 1)}
        onNext={() => goToPage(pageNumber + 1)}
        activePanel={mobilePanel}
        onTogglePanel={(panel) => setMobilePanel((p) => (p === panel ? null : panel))}
      >
        {mobilePanel === "search" && (
          <ViewerSearchPanel
            magazineId={magazineId}
            initialQuery={initialQuery}
            currentPage={pageNumber}
            onSelectHit={handleSelectHit}
          />
        )}
        {mobilePanel === "meta" && <ViewerMetaPanel magazine={magazine} />}
      </ViewerMobileNav>
    </div>
  );
}
