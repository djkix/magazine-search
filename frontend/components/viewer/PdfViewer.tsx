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

interface PageSize {
  width: number;
  height: number;
}

function PdfPage({
  doc,
  pageNumber,
  containerWidth,
  zoom,
  highlightWords,
  registerNode,
}: {
  doc: PDFDocumentProxy;
  pageNumber: number;
  containerWidth: number;
  zoom: number;
  highlightWords: WordBox[];
  registerNode: (pageNumber: number, node: HTMLDivElement | null) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<PageSize | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = wrapperRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) setVisible(true);
      },
      { rootMargin: "800px 0px" }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible || !containerWidth) return;
    let cancelled = false;
    let renderTask: { cancel: () => void; promise: Promise<void> } | null = null;

    async function render() {
      const page = await doc.getPage(pageNumber);
      if (cancelled) return;
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
    }

    render().catch(() => {});
    return () => {
      cancelled = true;
      renderTask?.cancel();
    };
  }, [doc, pageNumber, containerWidth, zoom, visible]);

  return (
    <div
      ref={(node) => {
        wrapperRef.current = node;
        registerNode(pageNumber, node);
      }}
      data-page-number={pageNumber}
      className="relative mx-auto mb-6 inline-block text-left"
      style={size ? { width: size.width, height: size.height } : { width: containerWidth - 48, height: (containerWidth - 48) * 1.3 }}
    >
      <canvas ref={canvasRef} className="block rounded-lg border border-outline-variant shadow-2xl shadow-black/40" />
      {size && highlightWords.length > 0 && (
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
  );
}

export default function PdfViewer({ fileUrl, pageNumber, zoom, highlightWords, onPageCount }: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const pageNodesRef = useRef<Map<number, HTMLDivElement>>(new Map());
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [containerWidth, setContainerWidth] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load the PDF document once per fileUrl.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDoc(null);
    setNumPages(0);

    async function load() {
      try {
        const pdfjsLib = await import("pdfjs-dist");
        pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

        const res = await fetch(fileUrl, { credentials: "include" });
        if (!res.ok) throw new Error("Impossible de charger le PDF");
        const data = await res.arrayBuffer();
        if (cancelled) return;

        const loadedDoc = await pdfjsLib.getDocument({ data }).promise;
        if (cancelled) return;
        setDoc(loadedDoc);
        setNumPages(loadedDoc.numPages);
        onPageCount?.(loadedDoc.numPages);
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

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    setContainerWidth(node.clientWidth);
    const observer = new ResizeObserver(() => setContainerWidth(node.clientWidth));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  // Scroll to the requested page whenever it changes externally (toolbar
  // prev/next, a search hit, or a sommaire entry) - free scrolling in
  // between doesn't fight this, it only reacts to pageNumber changing.
  useEffect(() => {
    if (loading) return;
    const target = pageNodesRef.current.get(pageNumber);
    target?.scrollIntoView({ behavior: "smooth", block: "start" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageNumber, loading]);

  return (
    <div ref={containerRef} className="h-full w-full overflow-auto p-6 text-center">
      {loading && (
        <p className="font-mono text-xs uppercase tracking-wider text-foreground-muted">Chargement du document...</p>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}
      {!loading && !error && doc && containerWidth > 0 && (
        <div>
          {Array.from({ length: numPages }, (_, i) => i + 1).map((n) => (
            <PdfPage
              key={n}
              doc={doc}
              pageNumber={n}
              containerWidth={containerWidth}
              zoom={zoom}
              highlightWords={n === pageNumber ? highlightWords : []}
              registerNode={(p, node) => {
                if (node) pageNodesRef.current.set(p, node);
                else pageNodesRef.current.delete(p);
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
