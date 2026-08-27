"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Category, Collection, GeminiSettings } from "@/lib/types";
import Button from "@/components/ui/Button";
import Icon from "@/components/ui/Icon";

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState<GeminiSettings | null>(null);
  const [selected, setSelected] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const [categories, setCategories] = useState<Category[]>([]);
  const [newCategory, setNewCategory] = useState("");
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);
  const [editingCategoryName, setEditingCategoryName] = useState("");
  const [categoryError, setCategoryError] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [reindexMessage, setReindexMessage] = useState<string | null>(null);

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
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur"));
  }

  function loadCategories() {
    api
      .get<Category[]>("/admin/categories")
      .then(setCategories)
      .catch((err) => setCategoryError(err instanceof ApiError ? err.message : "Erreur"));
  }

  function loadCollections() {
    api
      .get<Collection[]>("/admin/collections")
      .then(setCollections)
      .catch((err) => setCollectionError(err instanceof ApiError ? err.message : "Erreur"));
  }

  useEffect(load, []);
  useEffect(loadCategories, []);
  useEffect(loadCollections, []);

  async function createCategory() {
    if (!newCategory.trim()) return;
    setCategoryError(null);
    try {
      await api.post("/admin/categories", { name: newCategory.trim() });
      setNewCategory("");
      loadCategories();
    } catch (err) {
      setCategoryError(err instanceof ApiError ? err.message : "Erreur");
    }
  }

  async function saveCategory(id: number) {
    if (!editingCategoryName.trim()) return;
    try {
      await api.patch(`/admin/categories/${id}`, { name: editingCategoryName.trim() });
      setEditingCategoryId(null);
      loadCategories();
    } catch (err) {
      setCategoryError(err instanceof ApiError ? err.message : "Erreur");
    }
  }

  async function deleteCategory(id: number) {
    if (!window.confirm("Supprimer cette catégorie ? Les magazines associés ne seront plus catégorisés.")) return;
    await api.delete(`/admin/categories/${id}`);
    loadCategories();
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

  async function setCollectionCategory(id: number, categoryId: string) {
    try {
      await api.patch(`/admin/collections/${id}`, { category_id: categoryId ? Number(categoryId) : null });
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
      setCategoryError(err instanceof ApiError ? err.message : "Erreur");
    } finally {
      setReindexing(false);
    }
  }

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

      <div className="space-y-3 rounded-xl border border-outline-variant bg-surface/60 p-6">
        <div>
          <p className="text-sm font-medium text-foreground">Catégories</p>
          <p className="mt-1 text-xs text-foreground-muted">
            Thématiques (ex: "Bricolage", "Guide achat") utilisées pour filtrer la bibliothèque, les sommaires et la
            recherche. Chaque catégorie regroupe une ou plusieurs collections.
          </p>
        </div>

        {categoryError && <p className="text-sm text-red-400">{categoryError}</p>}

        <ul className="space-y-1">
          {categories.map((c) => (
            <li key={c.id} className="group flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-hover">
              {editingCategoryId === c.id ? (
                <input
                  value={editingCategoryName}
                  onChange={(e) => setEditingCategoryName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && saveCategory(c.id)}
                  autoFocus
                  className="min-w-0 flex-1 rounded-lg border border-outline-variant bg-background px-2 py-1 text-sm text-foreground"
                />
              ) : (
                <span className="text-sm text-foreground">{c.name}</span>
              )}
              <span className="hidden shrink-0 gap-2 group-hover:flex">
                {editingCategoryId === c.id ? (
                  <button onClick={() => saveCategory(c.id)} className="text-primary-light hover:underline">
                    <Icon name="check" className="text-sm" />
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      setEditingCategoryId(c.id);
                      setEditingCategoryName(c.name);
                    }}
                    className="text-foreground-muted hover:text-foreground"
                  >
                    <Icon name="edit" className="text-sm" />
                  </button>
                )}
                <button onClick={() => deleteCategory(c.id)} className="text-foreground-muted hover:text-red-400">
                  <Icon name="delete" className="text-sm" />
                </button>
              </span>
            </li>
          ))}
        </ul>

        <div className="flex gap-2 pt-2">
          <input
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createCategory()}
            placeholder="Nouvelle catégorie..."
            className="min-w-0 flex-1 rounded-lg border border-outline-variant bg-background px-3 py-2 text-sm text-foreground"
          />
          <Button onClick={createCategory} disabled={!newCategory.trim()} variant="secondary">
            Ajouter
          </Button>
        </div>
      </div>

      <div className="space-y-3 rounded-xl border border-outline-variant bg-surface/60 p-6">
        <div>
          <p className="text-sm font-medium text-foreground">Collections</p>
          <p className="mt-1 text-xs text-foreground-muted">
            Créées automatiquement au scan (une collection par répertoire du NAS, ex: "Que Choisir"). Rattache
            chaque collection à une catégorie pour que ses numéros soient inclus dans les recherches filtrées sur
            cette catégorie.
          </p>
        </div>

        {collectionError && <p className="text-sm text-red-400">{collectionError}</p>}

        <ul className="space-y-1">
          {collections.map((c) => (
            <li key={c.id} className="group flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 hover:bg-surface-hover">
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
              <select
                value={c.category_id ?? ""}
                onChange={(e) => setCollectionCategory(c.id, e.target.value)}
                className="shrink-0 rounded-lg border border-outline-variant bg-background px-2 py-1 text-xs text-foreground"
              >
                <option value="">Aucune catégorie</option>
                {categories.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.name}
                  </option>
                ))}
              </select>
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
            Réindexe tous les magazines déjà traités dans le moteur de recherche — utile après avoir catégorisé des
            magazines qui avaient été indexés avant l'ajout des catégories.
          </p>
        </div>
        {reindexMessage && <p className="text-sm text-emerald-400">{reindexMessage}</p>}
        <Button onClick={reindexAll} disabled={reindexing} variant="secondary">
          <Icon name="sync" className={reindexing ? "animate-spin" : ""} />
          {reindexing ? "Lancement..." : "Réindexer tous les magazines"}
        </Button>
      </div>
    </div>
  );
}
