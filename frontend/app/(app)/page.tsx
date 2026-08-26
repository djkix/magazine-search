"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import type { Magazine } from "@/lib/types";
import PageContainer from "@/components/layout/PageContainer";
import MagazineCard from "@/components/library/MagazineCard";
import Icon from "@/components/ui/Icon";

export default function HomePage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [recent, setRecent] = useState<Magazine[] | null>(null);

  useEffect(() => {
    api
      .get<Magazine[]>("/magazines?limit=8&sort=added")
      .then(setRecent)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) window.location.href = "/login";
      });
  }, []);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    router.push(`/search?q=${encodeURIComponent(q.trim())}`);
  }

  return (
    <PageContainer>
      <section className="mb-16 flex flex-col items-center py-12 text-center">
        <p className="mb-3 font-mono text-xs uppercase tracking-[0.2em] text-primary-light">Collection personnelle</p>
        <h1 className="mb-8 max-w-2xl font-serif text-4xl font-semibold text-foreground lg:text-5xl">
          Retrouvez chaque mot de vos magazines
        </h1>
        <form onSubmit={submit} className="w-full max-w-2xl">
          <div className="flex items-center gap-3 rounded-xl border border-outline-variant bg-surface/60 p-2 pl-5 backdrop-blur-sm transition focus-within:border-primary">
            <Icon name="search" className="text-foreground-muted" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Rechercher un mot, une expression..."
              className="flex-1 bg-transparent py-3 text-base text-foreground outline-none placeholder:text-foreground-muted/60"
            />
            <button
              type="submit"
              className="rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-white transition hover:bg-primary/90"
            >
              Rechercher
            </button>
          </div>
        </form>
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-foreground">Récemment ajoutés</h2>
          <Link href="/library" className="text-sm text-primary-light hover:underline">
            Voir la bibliothèque
          </Link>
        </div>

        {!recent && <p className="text-sm text-foreground-muted">Chargement...</p>}
        {recent?.length === 0 && <p className="text-sm text-foreground-muted">Aucun magazine indexé pour le moment.</p>}

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {recent?.map((m) => (
            <MagazineCard key={m.id} magazine={m} />
          ))}
        </div>
      </section>
    </PageContainer>
  );
}
