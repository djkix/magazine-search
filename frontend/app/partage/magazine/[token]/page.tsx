import type { Metadata } from "next";
import { headers } from "next/headers";
import PartageMagazineClient from "./PartageMagazineClient";

interface PartageMagazineInfo {
  magazine_title: string;
  collection_name: string | null;
}

const BACKEND = process.env.BACKEND_INTERNAL_URL || "http://app-backend:8000";

async function recupererInfo(token: string): Promise<PartageMagazineInfo | null> {
  try {
    const res = await fetch(`${BACKEND}/api/partage/magazine/${token}`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function origineePublique(): Promise<string> {
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

  return {
    title: info.magazine_title,
    description: info.collection_name ?? undefined,
    openGraph: {
      title: info.magazine_title,
      description: info.collection_name ?? undefined,
      images: [`${origine}/api/partage/magazine/${token}/cover`],
    },
  };
}

export default async function PartageMagazinePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <PartageMagazineClient token={token} />;
}
