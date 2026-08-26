"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";
import Button from "@/components/ui/Button";
import Icon from "@/components/ui/Icon";

export default function AdminUsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);

  function loadUsers() {
    api
      .get<User[]>("/admin/users")
      .then(setUsers)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Erreur"));
  }

  useEffect(loadUsers, []);

  async function toggleActive(user: User) {
    await api.patch(`/admin/users/${user.id}`, { is_active: !user.is_active });
    loadUsers();
  }

  async function resetPassword(user: User) {
    const newPassword = window.prompt(`Nouveau mot de passe pour ${user.email} :`);
    if (!newPassword) return;
    await api.post(`/admin/users/${user.id}/reset-password`, { new_password: newPassword });
    window.alert("Mot de passe réinitialisé. Communiquez-le directement à l'utilisateur.");
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-foreground">Utilisateurs</h1>
        <Button href="/admin/users/new">
          <Icon name="person_add" />
          Créer un nouvel utilisateur
        </Button>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="overflow-hidden rounded-xl border border-outline-variant">
        <table className="w-full text-sm">
          <thead className="bg-surface-hover text-left font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
            <tr>
              <th className="px-4 py-3">Utilisateur</th>
              <th className="px-4 py-3">Rôle</th>
              <th className="px-4 py-3">Statut</th>
              <th className="px-4 py-3">Dernière connexion</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant">
            {users.map((u) => (
              <tr key={u.id} className="bg-surface/40">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/15 font-mono text-[11px] text-primary-light">
                      {u.display_name.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-foreground">{u.display_name}</p>
                      <p className="truncate text-xs text-foreground-muted">{u.email}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-foreground-muted">{u.is_admin ? "Admin" : "Standard"}</td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider ${
                      u.is_active ? "bg-emerald-500/10 text-emerald-400" : "bg-foreground-muted/10 text-foreground-muted"
                    }`}
                  >
                    {u.is_active ? "Actif" : "Désactivé"}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-foreground-muted">
                  {u.last_login ? new Date(u.last_login).toLocaleString("fr-FR") : "—"}
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-3 text-xs">
                    <button onClick={() => toggleActive(u)} className="text-primary-light hover:underline">
                      {u.is_active ? "Désactiver" : "Réactiver"}
                    </button>
                    <button onClick={() => resetPassword(u)} className="text-primary-light hover:underline">
                      Réinitialiser mdp
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
