"use client";

import Link from "next/link";
import Icon from "@/components/ui/Icon";

export default function ViewerToolbar({
  title,
  subtitle,
  pageNumber,
  pageCount,
  zoom,
  onZoomIn,
  onZoomOut,
  onPrev,
  onNext,
  downloadHref,
  backHref,
}: {
  title: string;
  /** Ligne secondaire sous le titre (ex. magazine/collection) - la page de
   * partage publique l'utilise, le lecteur authentifié n'en a pas besoin. */
  subtitle?: string;
  pageNumber: number;
  pageCount: number;
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onPrev: () => void;
  onNext: () => void;
  /** Absent sur la page de partage publique : pas de téléchargement du
   * magazine entier proposé à qui n'a qu'un lien vers un seul article. */
  downloadHref?: string;
  /** Where the back arrow leads - the magazine's own collection, so the
   * reader lands back among its sibling issues rather than at the top of
   * the library. Falls back to the library for an unfiled magazine.
   * Absent sur la page de partage publique : rien à remonter vers, le
   * destinataire du lien n'a pas de compte. */
  backHref?: string;
}) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-outline-variant bg-surface/80 px-4 backdrop-blur-md">
      <div className="flex min-w-0 items-center gap-3">
        {backHref && (
          <Link
            href={backHref}
            className="rounded-lg p-1.5 text-foreground-muted transition hover:bg-surface-hover hover:text-foreground"
          >
            <Icon name="arrow_back" />
          </Link>
        )}
        <div className="min-w-0">
          <p className="truncate font-serif text-sm font-semibold text-foreground">{title}</p>
          {subtitle && <p className="truncate text-xs text-foreground-muted">{subtitle}</p>}
        </div>
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

        {downloadHref && (
          <>
            <div className="mx-2 h-5 w-px bg-outline-variant" />
            <a
              href={downloadHref}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-foreground-muted transition hover:bg-surface-hover hover:text-foreground"
            >
              <Icon name="download" />
              <span className="hidden sm:inline">Télécharger</span>
            </a>
          </>
        )}
      </div>
    </header>
  );
}
