"use client";

import Link from "next/link";
import Icon from "@/components/ui/Icon";

export default function ViewerToolbar({
  title,
  pageNumber,
  pageCount,
  zoom,
  onZoomIn,
  onZoomOut,
  onPrev,
  onNext,
  downloadHref,
}: {
  title: string;
  pageNumber: number;
  pageCount: number;
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onPrev: () => void;
  onNext: () => void;
  downloadHref: string;
}) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-outline-variant bg-surface/80 px-4 backdrop-blur-md">
      <div className="flex min-w-0 items-center gap-3">
        <Link
          href="/library"
          className="rounded-lg p-1.5 text-foreground-muted transition hover:bg-surface-hover hover:text-foreground"
        >
          <Icon name="arrow_back" />
        </Link>
        <p className="truncate font-serif text-sm font-semibold text-foreground">{title}</p>
      </div>

      <div className="flex items-center gap-1">
        <button
          onClick={onZoomOut}
          className="rounded-lg p-1.5 text-foreground-muted transition hover:bg-surface-hover hover:text-foreground"
        >
          <Icon name="remove" />
        </button>
        <span className="w-12 text-center font-mono text-xs text-foreground-muted">{Math.round(zoom * 100)}%</span>
        <button
          onClick={onZoomIn}
          className="rounded-lg p-1.5 text-foreground-muted transition hover:bg-surface-hover hover:text-foreground"
        >
          <Icon name="add" />
        </button>

        <div className="mx-2 h-5 w-px bg-outline-variant" />

        <button
          onClick={onPrev}
          disabled={pageNumber <= 1}
          className="rounded-lg p-1.5 text-foreground-muted transition hover:bg-surface-hover hover:text-foreground disabled:opacity-30"
        >
          <Icon name="chevron_left" />
        </button>
        <span className="font-mono text-xs text-foreground-muted">
          {pageNumber} / {pageCount || "—"}
        </span>
        <button
          onClick={onNext}
          disabled={!pageCount || pageNumber >= pageCount}
          className="rounded-lg p-1.5 text-foreground-muted transition hover:bg-surface-hover hover:text-foreground disabled:opacity-30"
        >
          <Icon name="chevron_right" />
        </button>

        <div className="mx-2 h-5 w-px bg-outline-variant" />

        <a
          href={downloadHref}
          className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-foreground-muted transition hover:bg-surface-hover hover:text-foreground"
        >
          <Icon name="download" />
          <span className="hidden sm:inline">Télécharger</span>
        </a>
      </div>
    </header>
  );
}
