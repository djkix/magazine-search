"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { GeminiSettings } from "@/lib/types";
import Button from "@/components/ui/Button";

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState<GeminiSettings | null>(null);
  const [selected, setSelected] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  function load() {
    api
      .get<GeminiSettings>("/admin/settings/gemini")
      .then((data) => {
        setSettings(data);
        setSelected(data.model);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur"));
  }

  useEffect(load, []);

  async function save() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const data = await api.put<GeminiSettings>("/admin/settings/gemini", { model: selected });
      setSettings(data);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur");
    } finally {
      setSaving(false);
    }
  }

  const isCustom = settings ? !settings.available_models.some((m) => m.id === selected) : false;

  return (
    <div className="max-w-xl space-y-6">
      <h1 className="text-xl font-semibold text-foreground">Réglages</h1>

      <div className="space-y-3 rounded-xl border border-outline-variant bg-surface/60 p-6">
        <div>
          <p className="text-sm font-medium text-foreground">Modèle Gemini (extraction des sommaires)</p>
          <p className="mt-1 text-xs text-foreground-muted">
            Utilisé pour extraire titre + page des articles depuis le sommaire OCRisé de chaque magazine.
          </p>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}
        {saved && <p className="text-sm text-emerald-400">Modèle enregistré.</p>}

        {settings && (
          <>
            <select
              value={isCustom ? "__custom__" : selected}
              onChange={(e) => setSelected(e.target.value === "__custom__" ? "" : e.target.value)}
              className="w-full rounded-lg border border-outline-variant bg-background px-3 py-2 text-sm text-foreground"
            >
              {settings.available_models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
              <option value="__custom__">Autre (identifiant personnalisé)...</option>
            </select>

            {(isCustom || selected === "") && (
              <input
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                placeholder="ex: gemini-3.1-pro"
                className="w-full rounded-lg border border-outline-variant bg-background px-3 py-2 text-sm text-foreground"
              />
            )}

            <Button onClick={save} disabled={saving || !selected}>
              {saving ? "Enregistrement..." : "Enregistrer"}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
