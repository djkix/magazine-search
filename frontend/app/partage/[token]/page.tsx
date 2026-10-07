import type { Metadata } from "next";
import { headers } from "next/headers";
import PartageClient from "./PartageClient";

interface PartageInfo {
  article_title: string;
  magazine_title: string;
  collection_name: string | null;
}

// Appel direct au backend, cote serveur, via le reseau Docker interne — pas
// par le navigateur, donc pas besoin de passer par /api et son proxy
// public. `cache: "no-store"` : chaque token a ses propres metadonnees, pas
// de cache a l'echelle de la route.
const BACKEND = process.env.BACKEND_INTERNAL_URL || "http://app-backend:8000";

async function recupererInfo(token: string): Promise<PartageInfo | null> {
  try {
    const res = await fetch(`${BACKEND}/api/partage/${token}`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function origineePublique(): Promise<string> {
  // Les en-tetes transmis par le reverse proxy (deja necessaires pour que
  // uvicorn connaisse sa propre origine publique, voir docker-compose.yml)
  // donnent l'URL que WhatsApp doit effectivement pouvoir atteindre -
  // jamais l'adresse interne du conteneur.
  const h = await headers();
  const host = h.get("host");
  const proto = h.get("x-forwarded-proto") ?? "https";
  return `${proto}://${host}`;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ token: string }>;
}): Promise<Metadata> {
  const { token } = await params;
  const info = await recupererInfo(token);
  if (!info) {
    return { title: "Lien introuvable" };
  }

  const origine = await origineePublique();
  const description = `${info.magazine_title}${info.collection_name ? ` · ${info.collection_name}` : ""}`;

  return {
    title: info.article_title,
    description,
    openGraph: {
      title: info.article_title,
      description,
      images: [`${origine}/api/partage/${token}/cover`],
    },
  };
}

export default async function PartagePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <PartageClient token={token} />;
}
