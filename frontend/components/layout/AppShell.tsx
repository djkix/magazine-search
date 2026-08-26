"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";
import Sidebar from "./Sidebar";
import BottomNav from "./BottomNav";
import { UserContext } from "./UserContext";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isViewer = pathname.startsWith("/viewer/");
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    api
      .get<User>("/me")
      .then(setUser)
      .catch((err) => {
        setUser(null);
        if (err instanceof ApiError && err.status === 401) {
          window.location.href = "/login";
        }
      });
  }, []);

  async function handleLogout() {
    try {
      await api.post("/logout");
    } finally {
      window.location.href = "/login";
    }
  }

  if (user === undefined) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="font-mono text-xs uppercase tracking-wider text-foreground-muted">Chargement...</p>
      </div>
    );
  }
  if (!user) return null;

  return (
    <UserContext.Provider value={user}>
      <div className="min-h-screen bg-background">
        <Sidebar user={user} onLogout={handleLogout} />
        {!isViewer && <BottomNav user={user} />}
        <main className={isViewer ? "lg:pl-64" : "pb-20 lg:pb-0 lg:pl-64"}>{children}</main>
      </div>
    </UserContext.Provider>
  );
}
