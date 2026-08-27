"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUser } from "@/components/layout/UserContext";

const TABS = [
  { href: "/admin", label: "Tableau de bord" },
  { href: "/admin/users", label: "Utilisateurs" },
  { href: "/admin/logs", label: "Logs" },
  { href: "/admin/settings", label: "Réglages" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const user = useUser();

  useEffect(() => {
    if (!user.is_admin) window.location.href = "/";
  }, [user.is_admin]);

  if (!user.is_admin) return null;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 lg:px-8">
      <div className="mb-8 flex items-center gap-1 border-b border-outline-variant">
        {TABS.map((tab) => {
          const active = tab.href === "/admin" ? pathname === "/admin" : pathname.startsWith(tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`border-b-2 px-4 py-3 text-sm transition ${
                active ? "border-primary text-foreground" : "border-transparent text-foreground-muted hover:text-foreground"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>
      {children}
    </div>
  );
}
