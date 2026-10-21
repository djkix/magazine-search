"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ClassificationStatus } from "@/lib/types";
import Icon from "@/components/ui/Icon";

const RAFRAICHISSEMENT_MS = 60_000;

function jourCalendaire(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

// « à 08:00 », « demain à 08:00 », ou la date complète au-delà, en heure locale.
function quand(jusqua: string, maintenant: Date = new Date()): string {
  const reprise = new Date(jusqua);
  if (reprise.getTime() - maintenant.getTime() < 90_000) return "dans moins d'une minute";
  const heure = reprise.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
  const ecartJours = Math.round((jourCalendaire(reprise) - jourCalendaire(maintenant)) / 86_400_000);
  if (ecartJours <= 0) return `à ${heure}`;
  if (ecartJours === 1) return `demain à ${heure}`;
  return `le ${reprise.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" })} à ${heure}`;
}

function messagePause(etat: ClassificationStatus, raison: string, jusqua: string): string {
  switch (raison) {
    case "quota_jour":
      return `Quota journalier Gemini atteint (${etat.requetes_aujourdhui}/${etat.limite_jour}). La classification reprend ${quand(jusqua)}.`;
    case "quota_minute":
      return `Limite par minute de Gemini atteinte : reprise ${quand(jusqua)}.`;
    case "cle_invalide":
      return "Clé API Gemini refusée : vérifiez GEMINI_API_KEY. Nouvelle tentative " + quand(jusqua) + ".";
    case "modele_introuvable":
      return `Modèle Gemini « ${etat.modele} » introuvable : vérifiez GEMINI_MODEL. Nouvelle tentative ${quand(jusqua)}.`;
    case "format_invalide":
      return `Les réponses de Gemini sont illisibles : nouvelle tentative ${quand(jusqua)}.`;
    default:
      return `Gemini est indisponible : nouvelle tentative ${quand(jusqua)}.`;
  }
}

export default function ClassificationBanner() {
  const [etat, setEtat] = useState<ClassificationStatus | null>(null);

  useEffect(() => {
    let annule = false;
    const charger = () =>
      api
        .get<ClassificationStatus>("/admin/classification")
        .then((d) => !annule && setEtat(d))
        .catch(() => !annule && setEtat(null));
    charger();
    const interval = setInterval(charger, RAFRAICHISSEMENT_MS);
    return () => {
      annule = true;
      clearInterval(interval);
    };
  }, []);

  if (!etat || !etat.actif) return null;

  if (etat.pause) {
    return (
      <div className="mb-6 flex items-start gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-300">
        <Icon name="pause_circle" className="mt-0.5 text-base" />
        <span>
          {messagePause(etat, etat.pause.raison, etat.pause.jusqua)}
          {etat.en_attente > 0 && ` ${etat.en_attente} article(s) en attente.`}
        </span>
      </div>
    );
  }

  if (etat.en_attente > 0) {
    return (
      <p className="mb-6 font-mono text-[11px] uppercase tracking-wider text-foreground-muted">
        {etat.en_attente} article(s) en attente de classification ({etat.requetes_aujourdhui}/{etat.limite_jour} requêtes aujourd&apos;hui)
      </p>
    );
  }

  return null;
}
