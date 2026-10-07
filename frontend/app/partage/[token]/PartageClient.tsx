"use client";

import { useEffect, useState } from "react";
import { api, ApiError, fileUrl } from "@/lib/api";
import PdfViewer from "@/components/viewer/PdfViewer";
import ViewerToolbar from "@/components/viewer/ViewerToolbar";

interface PartageInfo {
  article_title: string;
  magazine_title: string;
  collection_name: string | null;
  start_page: number;
  end_page: number | null;
}

// Reçoit `token` en prop plutôt que de le relire via useParams() : la page
// serveur (page.tsx) le connaît déjà pour generateMetadata, pas besoin de
// le dériver une seconde fois ici.
export default function PartageClient({ token }: { token: string }) {

  const [info, setInfo] = useState<PartageInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Démarre à 1, pas d'attente des métadonnées : le PDF commence à se
  // charger dès le montage, et saute à start_page dès que les métadonnées
  // arrivent — les deux requêtes (métadonnées, fichier) sont indépendantes,
  // les sérialiser coûterait un aller-retour réseau complet avant même la
  // première page, contraire à l'objectif de lecture rapide depuis un lien.
  const [pageNumber, setPageNumber] = useState(1);
  const [pageCount, setPageCount] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    api
      .get<PartageInfo>(`/partage/${token}`)
      .then((d) => {
        setInfo(d);
        setPageNumber(d.start_page);
      })
      .catch((err) => {
        // Seul un 404 signifie vraiment "ce lien n'existe plus" : une autre
        // erreur (backend temporairement indisponible, etc.) ne doit pas
        // laisser croire au destinataire que son lien est mort alors qu'un
        // simple rechargement suffirait.
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
        title={info ? info.article_title : "Chargement..."}
        subtitle={info ? `${info.magazine_title}${info.collection_name ? ` · ${info.collection_name}` : ""}` : undefined}
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
          fileUrl={fileUrl(`/partage/${token}/file`)}
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
