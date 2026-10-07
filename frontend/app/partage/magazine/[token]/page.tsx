import type { Metadata } from "next";
import { buildPartageMetadata } from "@/lib/partageMetadata";
import PartageMagazineClient from "./PartageMagazineClient";

interface PartageMagazineInfo {
  magazine_title: string;
  collection_name: string | null;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ token: string }>;
}): Promise<Metadata> {
  const { token } = await params;
  return buildPartageMetadata<PartageMagazineInfo>(
    `/api/partage/magazine/${token}`,
    `/api/partage/magazine/${token}/cover`,
    (info) => ({ title: info.magazine_title, description: info.collection_name ?? undefined })
  );
}

export default async function PartageMagazinePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <PartageMagazineClient token={token} />;
}
