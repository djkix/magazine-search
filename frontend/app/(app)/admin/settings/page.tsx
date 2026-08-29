"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Collection, GeminiSettings, Tag } from "@/lib/types";
import Button from "@/components/ui/Button";
import Icon from "@/components/ui/Icon";

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState<GeminiSettings | null>(null);
  const [selected, setSelected] = useState("");
  const [dailyLimit, setDailyLimit] = useState("");
  const [rpmLimit, setRpmLimit] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const [tags, setTags] = useState<Tag[]>([]);
  const [newTag, setNewTag] = useState("");
  const [editingTagId, setEditingTagId] = useState<number | null>(null);
  const [editingTagName, setEditingTagName] = useState("");
  const [tagError, setTagError] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [reindexMessage, setReindexMessage] = useState<string | null>(null);
  const [backfilling, setBackfilling] = useState(false);
  const [regeneratingThemes, setRegeneratingThemes] = useState(false);

  const [collections, setCollections] = useState<Collection[]>([]);
  const [editingCollectionId, setEditingCollectionId] = useState<number | null>(null);
  const [editingCollectionName, setEditingCollectionName] = useState("");
  const [collectionError, setCollectionError] = useState<string | null>(null);

  function load() {
    api
      .get<GeminiSettings>("/admin/settings/gemini")
      .then((data) => {
        setSettings(data);
        setSelected(data.model);
        setDailyLimit(data.daily_request_limit ? String(data.daily_request_limit) : "");
        setRpmLimit(data.rpm_limit ? String(data.rpm_limit) : "");
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur"));
  }

  function loadTags() {
    api
      .get<Tag[]>("/admin/tags")
      .then(setTags)
      .catch((err) => setTagError(err instanceof ApiError ? err.message : "Erreur"));
  }

  function loadCollections() {
    api
      .get<Collection[]>("/admin/collections")
      .then(setCollections)
      .catch((err) => setCollectionError(err instanceof ApiError ? err.message : "Erreur"));
  }

  useEffect(load, []);
  useEffect(loadTags, []);
  useEffect(loadCollections, []);

  async function createTag() {
    if (!newTag.trim()) return;
    setTagError(null);
    try {
      await api.post("/admin/tags", { name: newTag.trim() });
      setNewTag("");
      loadTags();
    } catch (err) {
      setTagError(err instanceof ApiError ? err.message : "Erreur");
    }
  }

  async function saveTag(id: number) {
    if (!editingTagName.trim()) return;
    try {
      await api.patch(`/admin/tags/${id}`, { name: editingTagName.trim() });
      setEditingTagId(null);
      loadTags();
      loadCollections();
    } catch (err) {
      setTagError(err instanceof ApiError ? err.message : "Erreur");
    }
  }

  async function deleteTag(id: number) {
    if (!window.confirm("Supprimer ce tag ? Les collections associées ne le porteront plus.")) return;
    await api.delete(`/admin/tags/${id}`);
    loadTags();
    loadCollections();
  }

  async function saveCollection(id: number) {
    if (!editingCollectionName.trim()) return;
    try {
      await api.patch(`/admin/collections/${id}`, { name: editingCollectionName.trim() });
      setEditingCollectionId(null);
      loadCollections();
    } catch (err) {
      setCollectionError(err instanceof ApiError ? err.message : "Erreur");
    }
  }

  async function toggleCollectionTag(collection: Collection, tagId: number) {
    const hasTag = collection.tags.some((t) => t.id === tagId);
    const tagIds = hasTag ? collection.tags.filter((t) => t.id !== tagId).map((t) => t.id) : [...collection.tags.map((t) => t.id), tagId];
    try {
      await api.put(`/admin/collections/${collection.id}/tags`, { tag_ids: tagIds });
      loadCollections();
    } catch (err) {
      setCollectionError(err instanceof ApiError ? err.message : "Erreur");
    }
  }

  async function deleteCollection(id: number) {
    if (!window.confirm("Supprimer cette collection ? Les magazines associés ne seront plus rattachés.")) return;
    await api.delete(`/admin/collections/${id}`);
    loadCollections();
  }

  async function reindexAll() {
    setReindexing(true);
    setReindexMessage(null);
    try {
      const data = await api.post<{ enqueued: number }>("/admin/search-index/reindex-all");
      setReindexMessage(`${data.enqueued} magazine(s) en cours de réindexation.`);
    } catch (err) {
      setTagError(err instanceof ApiError ? err.message : "Erreur");
    } finally {
      setReindexing(false);
    }
  }

  async function regenerateThemes() {
    setRegeneratingThemes(true);
    setReindexMessage(null);
    try {
      const data = await api.post<{ enqueued: number }>("/admin/themes/regenerate-all");
      setReindexMessage(`${data.enqueued} magazine(s) en cours de régénération des thématiques.`);
    } catch (err) {
      setTagError(err instanceof ApiError ? err.message : "Erreur");
    } finally {
      setRegeneratingThemes(false);
    }
  }

  async function backfillCollections() {
    setBackfilling(true);
    setReindexMessage(null);
    try {
      const data = await api.post<{ updated: number }>("/admin/collections/backfill");
      setReindexMessage(`${data.updated} magazine(s) recalculé(s).`);
      loadCollections();
    } catch (err) {
      setCollectionError(err instanceof ApiError ? err.message : "Erreur");
    } finally {
      setBackfilling(false);
    }
  }

  async function save() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const data = await api.put<GeminiSettings>("/admin/settings/gemini", {
        model: selected,
        daily_request_limit: dailyLimit.trim() ? Number(dailyLimit) : null,
        rpm_limit: rpmLimit.trim() ? Number(rpmLimit) : null,
      });
      setSettings(data);
      setDailyLimit(data.daily_request_limit ? String(data.daily_request_limit) : "");
      setRpmLimit(data.rpm_limit ? String(data.rpm_limit) : "");
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

            <div>
              <label className="text-xs text-foreground-muted">
                Quota Gemini (requêtes/jour, tous types confondus) — laisser vide si illimité (facturation activée)
              </label>
              <input
                type="number"
                min={0}
                value={dailyLimit}
                onChange={(e) => setDailyLimit(e.target.value)}
                placeholder="20"
                className="mt-1 w-full rounded-lg border border-outline-variant bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>

            <div>
              <label className="text-xs text-foreground-muted">
                Limite Gemini (requêtes/minute) — dépassée, l'app patiente au lieu d'insister ; laisser vide si illimité
              </label>
              <input
                type="number"
                min={0}
                value={rpmLimit}
                onChange={(e) => setRpmLimit(e.target.value)}
                placeholder="5"
                className="mt-1 w-full rounded-lg border border-outline-variant bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>

            <Button onClick={save} disabled={saving || !selected}>
              {saving ? "Enregistrement..." : "Enregistrer"}
            </Button>
          </>
        )}
      </div>

      <div className="space-y-3 rounded-xl border border-outline-variant bg-surface/60 p-6">
        <div>
          <p className="text-sm font-medium text-foreground">Tags</p>
          <p className="mt-1 text-xs text-foreground-muted">
            Thématiques (ex: "Bricolage", "Guide achat") utilisées pour filtrer la bibliothèque, les sommaires et la
            recherche. Un tag peut regrouper plusieurs collections, et une collection peut porter plusieurs tags.
          </p>
        </div>

        {tagError && <p className="text-sm text-red-400">{tagError}</p>}

        <ul className="space-y-1">
          {tags.map((t) => (
            <li key={t.id} className="group flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-hover">
              {editingTagId === t.id ? (
                <input
                  value={editingTagName}
                  onChange={(e) => setEditingTagName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && saveTag(t.id)}
                  autoFocus
                  className="min-w-0 flex-1 rounded-lg border border-outline-variant bg-background px-2 py-1 text-sm text-foreground"
                />
              ) : (
                <span className="text-sm text-foreground">{t.name}</span>
              )}
              <span className="hidden shrink-0 gap-2 group-hover:flex">
                {editingTagId === t.id ? (
                  <button onClick={() => saveTag(t.id)} className="text-primary-light hover:underline">
                    <Icon name="check" className="text-sm" />
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      setEditingTagId(t.id);
                      setEditingTagName(t.name);
                    }}
                    className="text-foreground-muted hover:text-foreground"
                  >
                    <Icon name="edit" className="text-sm" />
                  </button>
                )}
                <button onClick={() => deleteTag(t.id)} className="text-foreground-muted hover:text-red-400">
                  <Icon name="delete" className="text-sm" />
                </button>
              </span>
            </li>
          ))}
        </ul>

        <div className="flex gap-2 pt-2">
          <input
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createTag()}
            placeholder="Nouveau tag..."
            className="min-w-0 flex-1 rounded-lg border border-outline-variant bg-background px-3 py-2 text-sm text-foreground"
          />
          <Button onClick={createTag} disabled={!newTag.trim()} variant="secondary">
            Ajouter
          </Button>
        </div>
      </div>

      <div className="space-y-3 rounded-xl border border-outline-variant bg-surface/60 p-6">
        <div>
          <p className="text-sm font-medium text-foreground">Collections</p>
          <p className="mt-1 text-xs text-foreground-muted">
            Créées automatiquement au scan (une collection par répertoire du NAS, ex: "Que Choisir"). Clique sur un
            ou plusieurs tags pour les rattacher à la collection.
          </p>
        </div>

        {collectionError && <p className="text-sm text-red-400">{collectionError}</p>}

        <ul className="space-y-3">
          {collections.map((c) => (
            <li key={c.id} className="group rounded-lg px-2 py-2 hover:bg-surface-hover">
              <div className="flex items-center justify-between gap-2">
                {editingCollectionId === c.id ? (
                  <input
                    value={editingCollectionName}
                    onChange={(e) => setEditingCollectionName(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && saveCollection(c.id)}
                    autoFocus
                    className="min-w-0 flex-1 rounded-lg border border-outline-variant bg-background px-2 py-1 text-sm text-foreground"
                  />
                ) : (
                  <span className="min-w-0 flex-1 truncate text-sm text-foreground">{c.name}</span>
                )}
                <span className="hidden shrink-0 gap-2 group-hover:flex">
                  {editingCollectionId === c.id ? (
                    <button onClick={() => saveCollection(c.id)} className="text-primary-light hover:underline">
                      <Icon name="check" className="text-sm" />
                    </button>
                  ) : (
                    <button
                      onClick={() => {
                        setEditingCollectionId(c.id);
                        setEditingCollectionName(c.name);
                      }}
                      className="text-foreground-muted hover:text-foreground"
                    >
                      <Icon name="edit" className="text-sm" />
                    </button>
                  )}
                  <button onClick={() => deleteCollection(c.id)} className="text-foreground-muted hover:text-red-400">
                    <Icon name="delete" className="text-sm" />
                  </button>
                </span>
              </div>
              {tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {tags.map((t) => {
                    const active = c.tags.some((ct) => ct.id === t.id);
                    return (
                      <button
                        key={t.id}
                        onClick={() => toggleCollectionTag(c, t.id)}
                        className={`rounded-full px-2.5 py-1 text-[11px] transition ${
                          active
                            ? "bg-primary/20 text-primary-light"
                            : "bg-surface text-foreground-muted hover:bg-surface-hover"
                        }`}
                      >
                        {t.name}
                      </button>
                    );
                  })}
                </div>
              )}
            </li>
          ))}
        </ul>
        {collections.length === 0 && (
          <p className="text-sm text-foreground-muted">Aucune collection pour le moment — elles apparaissent après un scan du NAS.</p>
        )}
      </div>

      <div className="space-y-3 rounded-xl border border-outline-variant bg-surface/60 p-6">
        <div>
          <p className="text-sm font-medium text-foreground">Maintenance</p>
          <p className="mt-1 text-xs text-foreground-muted">
            Réindexe tous les magazines déjà traités dans le moteur de recherche — utile après avoir modifié des
            tags de collections déjà indexées.
          </p>
        </div>
        {reindexMessage && <p className="text-sm text-emerald-400">{reindexMessage}</p>}
        <div className="flex flex-wrap gap-2">
          <Button onClick={backfillCollections} disabled={backfilling} variant="secondary">
            <Icon name="folder_copy" className={backfilling ? "animate-spin" : ""} />
            {backfilling ? "Lancement..." : "Recalculer les collections et types de numéro"}
          </Button>
          <Button onClick={reindexAll} disabled={reindexing} variant="secondary">
            <Icon name="sync" className={reindexing ? "animate-spin" : ""} />
            {reindexing ? "Lancement..." : "Réindexer tous les magazines"}
          </Button>
          <Button onClick={regenerateThemes} disabled={regeneratingThemes} variant="secondary">
            <Icon name="sell" className={regeneratingThemes ? "animate-spin" : ""} />
            {regeneratingThemes ? "Lancement..." : "Régénérer les thématiques"}
          </Button>
        </div>
      </div>
    </div>
  );
}
