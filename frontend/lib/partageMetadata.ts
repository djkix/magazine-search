import type { Metadata } from "next";
import { headers } from "next/headers";

// Appel direct au backend, côté serveur, via le réseau Docker interne — pas
// par le navigateur, donc pas besoin de passer par /api et son proxy
// public. `cache: "no-store"` : chaque token a ses propres métadonnées, pas
// de cache à l'échelle de la route.
const BACKEND = process.env.BACKEND_INTERNAL_URL || "http://app-backend:8000";

async function origineePublique(): Promise<string> {
  // Les en-têtes transmis par le reverse proxy (déjà nécessaires pour que
  // uvicorn connaisse sa propre origine publique, voir docker-compose.yml)
  // donnent l'URL que WhatsApp doit effectivement pouvoir atteindre — jamais
  // l'adresse interne du conteneur.
  const h = await headers();
  const host = h.get("host");
  const proto = h.get("x-forwarded-proto") ?? "https";
  return `${proto}://${host}`;
}

/** Partagé par les deux pages de partage (article, numéro) : même logique
 * de récupération des métadonnées et de construction des balises Open
 * Graph, seuls le endpoint et la mise en forme titre/description diffèrent. */
export async function buildPartageMetadata<Info>(
  apiPath: string,
  coverPath: string,
  extraire: (info: Info) => { title: string; description?: string }
): Promise<Metadata> {
  let info: Info | null = null;
  try {
    const res = await fetch(`${BACKEND}${apiPath}`, { cache: "no-store" });
    if (res.ok) info = await res.json();
  } catch {
    info = null;
  }
  if (!info) {
    return { title: "Lien introuvable" };
  }

  const { title, description } = extraire(info);
  const origine = await origineePublique();

  return {
    title,
    description,
    openGraph: { title, description, images: [`${origine}${coverPath}`] },
  };
}
