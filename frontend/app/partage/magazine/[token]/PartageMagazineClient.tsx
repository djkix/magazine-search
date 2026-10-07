"use client";

import { useEffect, useState } from "react";
import { api, ApiError, fileUrl } from "@/lib/api";
import PdfViewer from "@/components/viewer/PdfViewer";
import ViewerToolbar from "@/components/viewer/ViewerToolbar";

interface PartageMagazineInfo {
  magazine_title: string;
  collection_name: string | null;
}

// Reçoit `token` en prop plutôt que de le relire via useParams() : la page
// serveur (page.tsx) le connaît déjà pour generateMetadata.
export default function PartageMagazineClient({ token }: { token: string }) {

  const [info, setInfo] = useState<PartageMagazineInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Pas d'attente des métadonnées avant de monter PdfViewer : les deux
  // requêtes (métadonnées, fichier) sont indépendantes, les sérialiser
  // coûterait un aller-retour réseau complet avant la première page.
  const [pageNumber, setPageNumber] = useState(1);
  const [pageCount, setPageCount] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    api
      .get<PartageMagazineInfo>(`/partage/magazine/${token}`)
      .then(setInfo)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setError("Ce lien n'est plus disponible.");
        } else {
          setError("Erreur de chargement. Réessayez.");
        }
      });
  }, [token]);

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-background p-8 text-center text-sm text-foreground-muted">
        {error}
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      <ViewerToolbar
        title={info ? info.magazine_title : "Chargement..."}
        subtitle={info?.collection_name ?? undefined}
        pageNumber={pageNumber}
        pageCount={pageCount ?? 0}
        zoom={zoom}
        onZoomIn={() => setZoom((z) => Math.min(2.5, +(z + 0.25).toFixed(2)))}
        onZoomOut={() => setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))}
        onPrev={() => setPageNumber((p) => Math.max(1, p - 1))}
        onNext={() => setPageNumber((p) => Math.min(pageCount ?? p, p + 1))}
      />

      <div className="relative flex-1 overflow-hidden">
        <PdfViewer
          fileUrl={fileUrl(`/partage/magazine/${token}/file`)}
          pageNumber={pageNumber}
          zoom={zoom}
          highlightWords={[]}
          onPageCount={setPageCount}
          onVisiblePageChange={setPageNumber}
          disableAutoFetch
        />
      </div>
    </div>
  );
}
