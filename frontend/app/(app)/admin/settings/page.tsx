"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Category, GeminiSettings } from "@/lib/types";
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

  useEffect(load, []);
  useEffect(loadCategories, []);

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
            Regroupe des magazines par thématique (ex: "Étude produit") pour filtrer la bibliothèque et les sommaires.
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
    </div>
  );
}
