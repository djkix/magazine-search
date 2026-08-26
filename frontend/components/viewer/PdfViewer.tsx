"use client";

import { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";
import type { WordBox } from "@/lib/types";

interface PdfViewerProps {
  fileUrl: string;
  pageNumber: number;
  zoom: number;
  highlightWords: WordBox[];
  onPageCount?: (count: number) => void;
}

export default function PdfViewer({ fileUrl, pageNumber, zoom, highlightWords, onPageCount }: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const docRef = useRef<PDFDocumentProxy | null>(null);
  const [size, setSize] = useState<{ width: number; height: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load (and parse) the PDF once per fileUrl.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSize(null);
    docRef.current = null;

    async function load() {
      try {
        const pdfjsLib = await import("pdfjs-dist");
        pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

        const res = await fetch(fileUrl, { credentials: "include" });
        if (!res.ok) throw new Error("Impossible de charger le PDF");
        const data = await res.arrayBuffer();
        if (cancelled) return;

        const doc = await pdfjsLib.getDocument({ data }).promise;
        if (cancelled) return;
        docRef.current = doc;
        onPageCount?.(doc.numPages);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Erreur de chargement du PDF");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileUrl]);

  // Render the requested page whenever the loaded doc, page number, or zoom changes.
  useEffect(() => {
    if (loading || !docRef.current) return;
    let cancelled = false;
    let renderTask: { cancel: () => void; promise: Promise<void> } | null = null;

    async function render() {
      try {
        const doc = docRef.current;
        if (!doc) return;
        const page = await doc.getPage(pageNumber);
        if (cancelled) return;

        const containerWidth = containerRef.current?.clientWidth ?? 800;
        const unscaledViewport = page.getViewport({ scale: 1 });
        const fitScale = Math.max((containerWidth - 48) / unscaledViewport.width, 0.1);
        const viewport = page.getViewport({ scale: fitScale * zoom });

        const canvas = canvasRef.current;
        if (!canvas) return;
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const context = canvas.getContext("2d");
        if (!context) return;

        renderTask = page.render({ canvasContext: context, viewport });
        await renderTask.promise;
        if (!cancelled) setSize({ width: viewport.width, height: viewport.height });
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Erreur d'affichage de la page");
      }
    }

    render();
    return () => {
      cancelled = true;
      renderTask?.cancel();
    };
  }, [pageNumber, zoom, loading]);

  return (
    <div ref={containerRef} className="h-full w-full overflow-auto p-6 text-center">
      {loading && (
        <p className="font-mono text-xs uppercase tracking-wider text-foreground-muted">Chargement du document...</p>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}
      {!loading && !error && (
        <div className="relative inline-block text-left" style={size ? { width: size.width, height: size.height } : undefined}>
          <canvas ref={canvasRef} className="block rounded-lg border border-outline-variant shadow-2xl shadow-black/40" />
          {size && (
            <div className="pointer-events-none absolute left-0 top-0" style={{ width: size.width, height: size.height }}>
              {highlightWords.map((word, i) => (
                <div
                  key={i}
                  className="absolute rounded-sm bg-primary/30 outline outline-2 outline-primary/70"
                  style={{
                    left: word.x * size.width,
                    top: word.y * size.height,
                    width: word.w * size.width,
                    height: word.h * size.height,
                  }}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
