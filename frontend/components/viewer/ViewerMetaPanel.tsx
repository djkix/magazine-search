"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Article, Magazine } from "@/lib/types";
import { useUser } from "@/components/layout/UserContext";
import Icon from "@/components/ui/Icon";
import Button from "@/components/ui/Button";

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

const TOC_STATUS_LABEL: Record<Magazine["toc_status"], string> = {
  pending: "Sommaire en attente",
  processing: "Extraction du sommaire...",
  done: "",
  failed: "Échec de l'extraction du sommaire",
};

export default function ViewerMetaPanel({
  magazine,
  onGoToPage,
}: {
  magazine: Magazine;
  onGoToPage: (page: number) => void;
}) {
  const user = useUser();
  const [articles, setArticles] = useState<Article[] | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [editingId, setEditingId] = useState<number | "new" | null>(null);
  const [form, setForm] = useState({ title: "", start_page: "", end_page: "" });

  function loadArticles() {
    api
      .get<Article[]>(`/magazines/${magazine.id}/articles`)
      .then(setArticles)
      .catch(() => setArticles([]));
  }

  useEffect(loadArticles, [magazine.id]);

  async function retryToc() {
    setRetrying(true);
    try {
      await api.post(`/admin/magazines/${magazine.id}/toc/retry`);
      window.setTimeout(loadArticles, 4000);
    } catch {
      // surfaced via magazine.toc_status on next load
    } finally {
      setRetrying(false);
    }
  }

  function startEdit(article?: Article) {
    if (article) {
      setEditingId(article.id);
      setForm({ title: article.title, start_page: String(article.start_page), end_page: String(article.end_page ?? "") });
    } else {
      setEditingId("new");
      setForm({ title: "", start_page: "", end_page: "" });
    }
  }

  async function saveArticle() {
    const payload = {
      title: form.title.trim(),
      start_page: Number(form.start_page),
      end_page: form.end_page ? Number(form.end_page) : null,
    };
    if (!payload.title || !payload.start_page) return;

    if (editingId === "new") {
      await api.post(`/admin/magazines/${magazine.id}/articles`, payload);
    } else if (editingId !== null) {
      await api.patch(`/admin/articles/${editingId}`, payload);
    }
    setEditingId(null);
    loadArticles();
  }

  async function deleteArticle(id: number) {
    if (!window.confirm("Supprimer cet article du sommaire ?")) return;
    await api.delete(`/admin/articles/${id}`);
    loadArticles();
  }

  const rows = [
    { label: "Titre", value: magazine.title },
    { label: "Numéro", value: magazine.issue_number ?? "—" },
    {
      label: "Date de publication",
      value: magazine.publication_date ? new Date(magazine.publication_date).toLocaleDateString("fr-FR") : "—",
    },
    { label: "Fichier", value: magazine.filename },
    { label: "Taille", value: formatSize(magazine.file_size) },
    { label: "Pages", value: String(magazine.page_count) },
  ];

  return (
    <div className="space-y-6 p-4">
      <div>
        <p className="mb-3 font-mono text-xs uppercase tracking-wider text-foreground-muted">Métadonnées</p>
        <dl className="space-y-3">
          {rows.map((row) => (
            <div key={row.label}>
              <dt className="font-mono text-[10px] uppercase tracking-wider text-foreground-muted">{row.label}</dt>
              <dd className="mt-0.5 truncate text-sm text-foreground">{row.value}</dd>
            </div>
          ))}
        </dl>
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <p className="font-mono text-xs uppercase tracking-wider text-foreground-muted">Sommaire</p>
          {user.is_admin && (
            <button onClick={() => startEdit()} className="text-primary-light hover:underline" title="Ajouter un article">
              <Icon name="add_circle" />
            </button>
          )}
        </div>

        {magazine.toc_status !== "done" && (
          <p className="mb-3 text-xs text-foreground-muted">
            {TOC_STATUS_LABEL[magazine.toc_status]}
            {magazine.toc_status === "failed" && user.is_admin && (
              <Button onClick={retryToc} disabled={retrying} variant="secondary" className="ml-2 py-1 text-xs">
                Réessayer
              </Button>
            )}
          </p>
        )}

        {editingId !== null && (
          <div className="mb-3 space-y-2 rounded-xl border border-outline-variant bg-surface p-3">
            <input
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="Titre de l'article"
              className="w-full rounded-lg border border-outline-variant bg-background px-2 py-1.5 text-sm text-foreground"
            />
            <div className="flex gap-2">
              <input
                value={form.start_page}
                onChange={(e) => setForm((f) => ({ ...f, start_page: e.target.value }))}
                placeholder="Page début"
                type="number"
                className="w-full rounded-lg border border-outline-variant bg-background px-2 py-1.5 text-sm text-foreground"
              />
              <input
                value={form.end_page}
                onChange={(e) => setForm((f) => ({ ...f, end_page: e.target.value }))}
                placeholder="Page fin"
                type="number"
                className="w-full rounded-lg border border-outline-variant bg-background px-2 py-1.5 text-sm text-foreground"
              />
            </div>
            <div className="flex justify-end gap-2 text-xs">
              <button onClick={() => setEditingId(null)} className="text-foreground-muted hover:underline">
                Annuler
              </button>
              <button onClick={saveArticle} className="text-primary-light hover:underline">
                Enregistrer
              </button>
            </div>
          </div>
        )}

        <ul className="space-y-1">
          {articles?.map((article) => (
            <li
              key={article.id}
              className="group flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-surface-hover"
            >
              <button onClick={() => onGoToPage(article.start_page)} className="min-w-0 flex-1 truncate text-left text-foreground">
                <span className="mr-2 font-mono text-[10px] text-foreground-muted">p.{article.start_page}</span>
                {article.title}
              </button>
              {user.is_admin && (
                <span className="hidden shrink-0 gap-1 group-hover:flex">
                  <button onClick={() => startEdit(article)} className="text-foreground-muted hover:text-foreground">
                    <Icon name="edit" className="text-sm" />
                  </button>
                  <button onClick={() => deleteArticle(article.id)} className="text-foreground-muted hover:text-red-400">
                    <Icon name="delete" className="text-sm" />
                  </button>
                </span>
              )}
            </li>
          ))}
          {articles?.length === 0 && magazine.toc_status === "done" && (
            <p className="text-sm text-foreground-muted">Aucun sommaire détecté.</p>
          )}
        </ul>
      </div>
    </div>
  );
}
