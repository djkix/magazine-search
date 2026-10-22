"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { PartageActif } from "@/lib/types";

// Liens publics encore valides, du plus proche de l'expiration au plus
// lointain. Révoquer coupe le lien immédiatement : un nouveau partage de la
// même ressource produira une autre URL, l'ancienne ne revient jamais.
export default function AdminPartagesPage() {
  const [liens, setLiens] = useState<PartageActif[]>([]);
  const [error, setError] = useState<string | null>(null);

  function charger() {
    api
      .get<PartageActif[]>("/admin/partages")
      .then(setLiens)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur"));
  }

  useEffect(charger, []);

  async function revoquer(lien: PartageActif) {
    if (!window.confirm(`Révoquer le lien vers « ${lien.title} » ? Il cessera de fonctionner immédiatement.`)) return;
    const chemin = lien.kind === "article" ? `/articles/${lien.id}/share` : `/magazines/${lien.id}/share`;
    try {
      await api.delete(chemin);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur");
    }
    charger();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Liens de partage actifs</h1>
        <p className="mt-1 text-sm text-foreground-muted">
          Accessibles sans compte jusqu&apos;à leur expiration. Révoquez tout lien qui n&apos;a plus lieu d&apos;être.
        </p>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {liens.length === 0 ? (
        <p className="text-sm text-foreground-muted">Aucun lien actif.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-outline-variant">
          <table className="w-full text-sm">
            <thead className="bg-surface-hover text-left font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
              <tr>
                <th className="px-4 py-3">Contenu</th>
                <th className="px-4 py-3">Créé par</th>
                <th className="px-4 py-3">Expire le</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant">
              {liens.map((lien) => (
                <tr key={`${lien.kind}-${lien.id}`} className="bg-surface/40">
                  <td className="px-4 py-3">
                    <p className="text-foreground">{lien.title}</p>
                    <p className="text-xs text-foreground-muted">
                      {lien.kind === "article" ? `Article · ${lien.magazine_title}` : "Numéro entier"}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-xs text-foreground-muted">{lien.created_by_email ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs text-foreground-muted">
                    {new Date(lien.expires_at).toLocaleString("fr-FR")}
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => revoquer(lien)} className="text-xs text-red-400 hover:underline">
                      Révoquer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
