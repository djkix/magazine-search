"use client";

import type { ReactNode } from "react";
import Icon from "@/components/ui/Icon";

type Panel = "search" | "meta";

export default function ViewerMobileNav({
  pageNumber,
  pageCount,
  onPrev,
  onNext,
  activePanel,
  onTogglePanel,
  children,
}: {
  pageNumber: number;
  pageCount: number;
  onPrev: () => void;
  onNext: () => void;
  activePanel: Panel | null;
  onTogglePanel: (panel: Panel) => void;
  children?: ReactNode;
}) {
  return (
    <div className="lg:hidden">
      {activePanel && (
        <div className="fixed inset-x-0 bottom-[68px] z-40 max-h-[60vh] overflow-hidden rounded-t-2xl border-t border-outline-variant bg-surface shadow-2xl">
          {children}
        </div>
      )}

      <div className="fixed inset-x-0 bottom-0 z-40 flex items-center justify-between gap-2 border-t border-outline-variant bg-surface/95 px-4 py-3 backdrop-blur-md">
        <button
          onClick={onPrev}
          disabled={pageNumber <= 1}
          className="rounded-full bg-surface-hover p-2.5 text-foreground disabled:opacity-30"
        >
          <Icon name="chevron_left" />
        </button>

        <div className="flex items-center gap-2">
          <button
            onClick={() => onTogglePanel("search")}
            className={`flex items-center gap-1.5 rounded-full px-3 py-2 text-xs ${
              activePanel === "search" ? "bg-primary text-white" : "bg-surface-hover text-foreground-muted"
            }`}
          >
            <Icon name="search" className="text-base" />
            Recherche
          </button>
          <button
            onClick={() => onTogglePanel("meta")}
            className={`flex items-center gap-1.5 rounded-full px-3 py-2 text-xs ${
              activePanel === "meta" ? "bg-primary text-white" : "bg-surface-hover text-foreground-muted"
            }`}
          >
            <Icon name="info" className="text-base" />
            Infos
          </button>
        </div>

        <button
          onClick={onNext}
          disabled={pageNumber >= pageCount}
          className="rounded-full bg-surface-hover p-2.5 text-foreground disabled:opacity-30"
        >
          <Icon name="chevron_right" />
        </button>
      </div>
    </div>
  );
}
