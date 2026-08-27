"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { LibraryOverview } from "@/lib/types";
import PageContainer from "@/components/layout/PageContainer";
import CollectionCard from "@/components/library/CollectionCard";

export default function ArticlesPage() {
  const [overview, setOverview] = useState<LibraryOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<LibraryOverview>("/collections")
      .then(setOverview)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) window.location.href = "/login";
      })
      .finally(() => setLoading(false));
  }, []);

  const isEmpty = !loading && (overview?.collections.length ?? 0) === 0 && (overview?.unassigned_count ?? 0) === 0;

  return (
    <PageContainer>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-foreground">Sommaires</h1>
        <p className="mt-1 text-sm text-foreground-muted">Choisissez une collection pour parcourir ses sommaires.</p>
      </div>

      {isEmpty && <p className="text-sm text-foreground-muted">Aucun magazine indexé pour le moment.</p>}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        {overview?.collections.map((c) => (
          <CollectionCard
            key={c.id}
            href={`/articles/collection/${c.id}`}
            name={c.name}
            count={c.magazine_count}
            coverMagazineId={c.cover_magazine_id}
          />
        ))}
        {overview && overview.unassigned_count > 0 && (
          <CollectionCard
            href="/articles/collection/none"
            name="Sans collection"
            count={overview.unassigned_count}
            coverMagazineId={overview.unassigned_cover_magazine_id}
          />
        )}
      </div>
    </PageContainer>
  );
}
