"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { api, ApiError, redirectToLogin } from "@/lib/api";
import type { User } from "@/lib/types";
import Sidebar from "./Sidebar";
import BottomNav from "./BottomNav";
import { UserContext } from "./UserContext";

// Clé de persistance du repli. Le choix doit survivre à la navigation et au
// rechargement : le refaire à chaque page serait plus agaçant qu'utile.
const CLE_REPLI = "sidebar-replie";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isViewer = pathname.startsWith("/viewer/");
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [replie, setReplie] = useState(false);

  // Lu APRÈS le montage, jamais pendant le rendu : le serveur n'a pas accès à
  // localStorage, et lire ici éviterait une divergence d'hydratation entre le
  // HTML rendu côté serveur et le premier rendu du navigateur.
  useEffect(() => {
    setReplie(window.localStorage.getItem(CLE_REPLI) === "1");
  }, []);

  function basculerSidebar() {
    setReplie((actuel) => {
      const suivant = !actuel;
      window.localStorage.setItem(CLE_REPLI, suivant ? "1" : "0");
      return suivant;
    });
  }

  useEffect(() => {
    api
      .get<User>("/me")
      .then(setUser)
      .catch((err) => {
        setUser(null);
        if (err instanceof ApiError && err.status === 401) {
          redirectToLogin();
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
      <SidebarContext.Provider value={replie}>
        <div className="min-h-screen bg-background">
          <Sidebar user={user} onLogout={handleLogout} replie={replie} onBasculer={basculerSidebar} />
          {!isViewer && <BottomNav user={user} />}
          {/* La marge du contenu suit la largeur de la barre : sans cela, replier
              laisserait une bande vide de 12 rem à gauche. La transition est la
              même que celle de la barre, pour que les deux bougent ensemble. */}
          <main
            className={`transition-[padding] duration-200 ${replie ? "lg:pl-16" : "lg:pl-64"} ${
              isViewer ? "" : "pb-20 lg:pb-0"
            }`}
          >
            {children}
          </main>
        </div>
      </SidebarContext.Provider>
    </UserContext.Provider>
  );
}
