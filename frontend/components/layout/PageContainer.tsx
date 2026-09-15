"use client";

import type { ReactNode } from "react";
import { useSidebarReplie } from "./SidebarContext";

export default function PageContainer({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  const replie = useSidebarReplie();

  // Barre dépliée : contenu centré et borné à 72 rem, longueur de ligne
  // confortable à lire.
  //
  // Barre repliée : `mx-auto` absorberait tout l'espace libéré dans les marges
  // automatiques et le contenu ne bougerait pas d'un pixel — replier la barre
  // n'aurait alors aucun effet visible. On colle donc à gauche et on lève le
  // plafond, pour que la place gagnée serve réellement au contenu.
  const largeur = replie ? "max-w-none" : "mx-auto max-w-6xl";

  return <div className={`${largeur} px-4 py-8 lg:px-8 ${className}`}>{children}</div>;
}
