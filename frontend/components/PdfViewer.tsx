"use client";

import { useEffect, useRef, useState } from "react";
import type { WordBox } from "@/lib/types";

export default function PdfViewer({
  fileUrl,
  pageNumber,
  highlightWords,
}: {
  fileUrl: string;
  pageNumber: number;
  highlightWords: WordBox[];
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<{ width: number; height: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let renderTask: { cancel: () => void } | null = null;

    async function render() {
      setError(null);
      try {
        const pdfjsLib = await import("pdfjs-dist");
        pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
          "pdfjs-dist/build/pdf.worker.min.mjs",
          import.meta.url
        ).toString();

        const res = await fetch(fileUrl, { credentials: "include" });
        if (!res.ok) throw new Error("Impossible de charger le PDF");
        const data = await res.arrayBuffer();
        if (cancelled) return;

        const doc = await pdfjsLib.getDocument({ data }).promise;
        const page = await doc.getPage(pageNumber);
        if (cancelled) return;

        const containerWidth = containerRef.current?.clientWidth ?? 800;
        const unscaledViewport = page.getViewport({ scale: 1 });
        const scale = containerWidth / unscaledViewport.width;
        const viewport = page.getViewport({ scale });

        const canvas = canvasRef.current;
        if (!canvas) return;
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        const context = canvas.getContext("2d");
        if (!context) return;

        renderTask = page.render({ canvasContext: context, viewport });
        await renderTask.promise;
        if (!cancelled) {
          setSize({ width: viewport.width, height: viewport.height });
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Erreur d'affichage du PDF");
        }
      }
    }

    render();
    return () => {
      cancelled = true;
      renderTask?.cancel();
    };
  }, [fileUrl, pageNumber]);

  return (
    <div ref={containerRef} className="relative w-full">
      {error && <p className="text-sm text-red-600">{error}</p>}
      <canvas ref={canvasRef} className="w-full rounded border shadow-sm" />
      {size && (
        <div
          className="pointer-events-none absolute left-0 top-0"
          style={{ width: size.width, height: size.height }}
        >
          {highlightWords.map((word, i) => (
            <div
              key={i}
              className="absolute rounded-sm bg-yellow-300/50 outline outline-1 outline-yellow-500"
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
