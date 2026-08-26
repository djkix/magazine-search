"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

export default function Navbar() {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    api
      .get<User>("/me")
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  async function logout() {
    await api.post("/logout");
    window.location.href = "/login";
  }

  if (user === undefined) {
    return <nav className="border-b bg-white px-4 py-3" />;
  }

  return (
    <nav className="flex items-center justify-between border-b bg-white px-4 py-3">
      <Link href="/" className="font-semibold text-slate-800">
        Magazine Search
      </Link>
      {user && (
        <div className="flex items-center gap-4 text-sm">
          <Link href="/" className="hover:underline">
            Recherche
          </Link>
          {user.is_admin && (
            <Link href="/admin" className="hover:underline">
              Backoffice
            </Link>
          )}
          <span className="text-slate-500">{user.display_name}</span>
          <button onClick={logout} className="text-red-600 hover:underline">
            Déconnexion
          </button>
        </div>
      )}
    </nav>
  );
}
