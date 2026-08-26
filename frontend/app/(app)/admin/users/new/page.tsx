"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import Input from "@/components/ui/Input";
import Button from "@/components/ui/Button";
import Icon from "@/components/ui/Icon";

export default function NewUserPage() {
  const router = useRouter();
  const [form, setForm] = useState({ display_name: "", email: "", password: "", is_admin: false });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.post("/admin/users", form);
      router.push("/admin/users");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur de création");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Créer un utilisateur</h1>
        <p className="mt-1 text-sm text-foreground-muted">
          Le mot de passe est défini ici par vos soins et doit être communiqué directement à la personne concernée,
          en dehors de l&apos;application.
        </p>
      </div>

      <form onSubmit={submit} className="space-y-5 rounded-xl border border-outline-variant bg-surface/60 p-6 backdrop-blur-sm">
        <Input
          id="display_name"
          label="Nom affiché"
          required
          value={form.display_name}
          onChange={(e) => setForm({ ...form, display_name: e.target.value })}
        />
        <Input
          id="email"
          label="Email"
          type="email"
          required
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
        <Input
          id="password"
          label="Mot de passe"
          type="password"
          required
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />

        <div>
          <p className="mb-2 font-mono text-xs uppercase tracking-wider text-foreground-muted">Rôle</p>
          <div className="grid grid-cols-2 gap-3">
            <RoleCard
              icon="person"
              title="Standard"
              description="Recherche, consultation et téléchargement."
              selected={!form.is_admin}
              onClick={() => setForm({ ...form, is_admin: false })}
            />
            <RoleCard
              icon="admin_panel_settings"
              title="Admin"
              description="Accès complet + backoffice et scan du NAS."
              selected={form.is_admin}
              onClick={() => setForm({ ...form, is_admin: true })}
            />
          </div>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <div className="flex items-center gap-3 pt-2">
          <Button type="submit" disabled={loading}>
            {loading ? "Création..." : "Créer le compte"}
          </Button>
          <Button href="/admin/users" variant="ghost">
            Annuler
          </Button>
        </div>
      </form>
    </div>
  );
}

function RoleCard({
  icon,
  title,
  description,
  selected,
  onClick,
}: {
  icon: string;
  title: string;
  description: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-xl border p-4 text-left transition ${
        selected ? "border-primary bg-primary/5" : "border-outline-variant bg-surface hover:border-primary/50"
      }`}
    >
      <Icon name={icon} className={selected ? "text-primary-light" : "text-foreground-muted"} />
      <p className="mt-2 text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 text-xs text-foreground-muted">{description}</p>
    </button>
  );
}
