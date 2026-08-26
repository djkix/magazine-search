"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { ScanStatusResponse, ScanTriggerResponse, User } from "@/lib/types";

export default function AdminPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [newUser, setNewUser] = useState({ email: "", display_name: "", password: "", is_admin: false });
  const [scanJob, setScanJob] = useState<ScanStatusResponse | null>(null);
  const [scanning, setScanning] = useState(false);

  function loadUsers() {
    api
      .get<User[]>("/admin/users")
      .then(setUsers)
      .catch((err) => {
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          window.location.href = "/";
          return;
        }
        setError(err instanceof ApiError ? err.message : "Erreur");
      });
  }

  useEffect(loadUsers, []);

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post("/admin/users", newUser);
      setNewUser({ email: "", display_name: "", password: "", is_admin: false });
      loadUsers();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur de création");
    }
  }

  async function toggleActive(user: User) {
    await api.patch(`/admin/users/${user.id}`, { is_active: !user.is_active });
    loadUsers();
  }

  async function resetPassword(user: User) {
    const newPassword = window.prompt(`Nouveau mot de passe pour ${user.email} :`);
    if (!newPassword) return;
    await api.post(`/admin/users/${user.id}/reset-password`, { new_password: newPassword });
    window.alert("Mot de passe réinitialisé. Communiquez-le à l'utilisateur.");
  }

  async function triggerScan() {
    setScanning(true);
    setError(null);
    try {
      const trigger = await api.post<ScanTriggerResponse>("/admin/scan");
      pollScan(trigger.job_id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erreur de scan");
      setScanning(false);
    }
  }

  function pollScan(jobId: string) {
    const interval = setInterval(async () => {
      try {
        const status = await api.get<ScanStatusResponse>(`/admin/scan/${jobId}/status`);
        setScanJob(status);
        if (status.finished) {
          clearInterval(interval);
          setScanning(false);
        }
      } catch {
        clearInterval(interval);
        setScanning(false);
      }
    }, 3000);
  }

  return (
    <div className="space-y-10">
      {error && <p className="text-sm text-red-600">{error}</p>}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Scan du NAS</h2>
          <button
            onClick={triggerScan}
            disabled={scanning}
            className="rounded bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {scanning ? "Scan en cours..." : "Scanner le NAS"}
          </button>
        </div>
        {scanJob && (
          <div className="rounded border bg-white p-4 text-sm">
            <p>Job : {scanJob.job_id}</p>
            <p>Détectés : {scanJob.detected} · En cours : {scanJob.processing} · Terminés : {scanJob.done} · Échecs : {scanJob.failed}</p>
            <p>{scanJob.finished ? "Terminé" : "En cours..."}</p>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Créer un compte</h2>
        <form onSubmit={createUser} className="flex flex-wrap items-end gap-2 rounded border bg-white p-4">
          <div>
            <label className="mb-1 block text-xs text-slate-500">Email</label>
            <input
              type="email"
              required
              value={newUser.email}
              onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
              className="rounded border px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Nom affiché</label>
            <input
              type="text"
              required
              value={newUser.display_name}
              onChange={(e) => setNewUser({ ...newUser, display_name: e.target.value })}
              className="rounded border px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Mot de passe</label>
            <input
              type="password"
              required
              value={newUser.password}
              onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
              className="rounded border px-3 py-1.5 text-sm"
            />
          </div>
          <label className="flex items-center gap-1 text-sm">
            <input
              type="checkbox"
              checked={newUser.is_admin}
              onChange={(e) => setNewUser({ ...newUser, is_admin: e.target.checked })}
            />
            Admin
          </label>
          <button type="submit" className="rounded bg-slate-800 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-700">
            Créer
          </button>
        </form>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Comptes</h2>
        <table className="w-full rounded border bg-white text-sm">
          <thead className="border-b bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">Nom</th>
              <th className="px-3 py-2">Rôle</th>
              <th className="px-3 py-2">Statut</th>
              <th className="px-3 py-2">Dernière connexion</th>
              <th className="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b last:border-0">
                <td className="px-3 py-2">{u.email}</td>
                <td className="px-3 py-2">{u.display_name}</td>
                <td className="px-3 py-2">{u.is_admin ? "Admin" : "Standard"}</td>
                <td className="px-3 py-2">{u.is_active ? "Actif" : "Désactivé"}</td>
                <td className="px-3 py-2">{u.last_login ? new Date(u.last_login).toLocaleString("fr-FR") : "—"}</td>
                <td className="flex gap-2 px-3 py-2">
                  <button onClick={() => toggleActive(u)} className="text-blue-600 hover:underline">
                    {u.is_active ? "Désactiver" : "Réactiver"}
                  </button>
                  <button onClick={() => resetPassword(u)} className="text-blue-600 hover:underline">
                    Reset mdp
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
