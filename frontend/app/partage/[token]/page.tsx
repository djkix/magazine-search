import type { Metadata } from "next";
import { buildPartageMetadata } from "@/lib/partageMetadata";
import PartageClient from "./PartageClient";

interface PartageInfo {
  article_title: string;
  magazine_title: string;
  collection_name: string | null;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ token: string }>;
}): Promise<Metadata> {
  const { token } = await params;
  return buildPartageMetadata<PartageInfo>(`/api/partage/${token}`, `/api/partage/${token}/cover`, (info) => ({
    title: info.article_title,
    description: `${info.magazine_title}${info.collection_name ? ` · ${info.collection_name}` : ""}`,
  }));
}

export default async function PartagePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <PartageClient token={token} />;
}
