"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SauvegardeStatus } from "@/lib/types";
import Button from "@/components/ui/Button";
import Icon from "@/components/ui/Icon";

const RAFRAICHISSEMENT_MS = 60_000;

function date(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

/**
 * Sauvegarde vers le NAS : alerte si la dernière tentative a échoué ou si
 * rien n'a réussi depuis 36 h, et « Sauvegarder maintenant ». Rien tant que
 * le service n'a jamais tourné (installation sans NAS de sauvegarde).
 */
export default function SauvegardeBanner() {
  const [etat, setEtat] = useState<SauvegardeStatus | null>(null);
  const [envoi, setEnvoi] = useState(false);

  const charger = () =>
    api
      .get<SauvegardeStatus>("/admin/backup")
      .then(setEtat)
      .catch(() => setEtat(null));

  useEffect(() => {
    charger();
    const interval = setInterval(charger, RAFRAICHISSEMENT_MS);
    return () => clearInterval(interval);
  }, []);

  async function demander() {
    setEnvoi(true);
    try {
      await api.post("/admin/backup/request");
      await charger();
    } finally {
      setEnvoi(false);
    }
  }

  if (!etat || !etat.derniere_tentative) return null;

  return (
    <div
      className={`mb-6 flex flex-wrap items-center gap-3 rounded-lg border p-3 text-sm ${
        etat.alerte ? "border-amber-500/40 bg-amber-500/10 text-amber-300" : "border-outline-variant text-foreground-muted"
      }`}
    >
      <Icon name={etat.alerte ? "warning" : "backup"} className="text-base" />
      <span className="flex-1">
        {etat.alerte ?? "Sauvegarde vers le NAS à jour."}
        {etat.derniere_reussite && ` Dernière réussie le ${date(etat.derniere_reussite)}.`}
      </span>
      {etat.demandee ? (
        <span className="font-mono text-[11px] uppercase tracking-wider">Demandée, part dans les 5 minutes</span>
      ) : (
        <Button variant="secondary" onClick={demander} disabled={envoi}>
          Sauvegarder maintenant
        </Button>
      )}
    </div>
  );
}
