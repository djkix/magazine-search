"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Icon from "@/components/ui/Icon";
import type { User } from "@/lib/types";

const NAV_ITEMS = [
  { href: "/", label: "Recherche", icon: "search" },
  { href: "/library", label: "Bibliothèque", icon: "collections_bookmark" },
  { href: "/articles", label: "Sommaires", icon: "toc" },
];

export default function Sidebar({ user, onLogout }: { user: User; onLogout: () => void }) {
  const pathname = usePathname();
  const items = user.is_admin ? [...NAV_ITEMS, { href: "/admin", label: "Admin", icon: "admin_panel_settings" }] : NAV_ITEMS;

  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-outline-variant bg-surface/80 backdrop-blur-md lg:flex">
      <div className="flex items-center gap-2 px-6 py-6">
        <Icon name="auto_stories" className="text-2xl text-primary" />
        <span className="font-serif text-lg font-semibold text-foreground">L&apos;Archive</span>
        {process.env.NEXT_PUBLIC_APP_VERSION && (
          <span className="ml-auto font-mono text-[10px] text-foreground-muted">
            v{process.env.NEXT_PUBLIC_APP_VERSION}
          </span>
        )}
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {items.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${
                active ? "bg-primary/10 text-primary-light" : "text-foreground-muted hover:bg-surface-hover hover:text-foreground"
              }`}
            >
              <Icon name={item.icon} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-outline-variant p-4">
        <div className="mb-2 flex items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/20 font-mono text-xs text-primary-light">
            {user.display_name.slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm text-foreground">{user.display_name}</p>
            <p className="truncate font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
              {user.is_admin ? "Admin" : "Standard"}
            </p>
          </div>
        </div>
        <button
          onClick={onLogout}
          className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-foreground-muted transition hover:bg-surface-hover hover:text-foreground"
        >
          <Icon name="logout" />
          Déconnexion
        </button>
      </div>
    </aside>
  );
}
