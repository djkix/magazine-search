"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Icon from "@/components/ui/Icon";
import type { User } from "@/lib/types";

// Thématiques avant Sommaires : on cherche d'abord un sujet, et on descend
// ensuite au sommaire d'un numéro précis.
export const NAV_ITEMS = [
  { href: "/library", label: "Bibliothèque", icon: "collections_bookmark" },
  { href: "/themes", label: "Thématiques", icon: "label" },
  { href: "/articles", label: "Sommaires", icon: "toc" },
  { href: "/", label: "Recherche", icon: "search" },
];

export default function Sidebar({
  user,
  onLogout,
  replie,
  onBasculer,
}: {
  user: User;
  onLogout: () => void;
  replie: boolean;
  onBasculer: () => void;
}) {
  const pathname = usePathname();
  const items = user.is_admin
    ? [...NAV_ITEMS, { href: "/admin", label: "Admin", icon: "admin_panel_settings" }]
    : NAV_ITEMS;

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-outline-variant bg-surface/80 backdrop-blur-md transition-[width] duration-200 lg:flex ${
        replie ? "w-16" : "w-64"
      }`}
    >
      <Link
        href="/"
        className={`flex items-center gap-2 py-6 ${replie ? "justify-center px-0" : "px-6"}`}
        title={replie ? "L'Archive" : undefined}
      >
        <Icon name="auto_stories" className="shrink-0 text-2xl text-primary" />
        {!replie && (
          <span className="font-serif text-lg font-semibold text-foreground">L&apos;Archive</span>
        )}
      </Link>

      <nav className={`flex-1 space-y-1 ${replie ? "px-2" : "px-3"}`}>
        {items.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              // L'infobulle est le seul libellé restant une fois replié :
              // sans elle, les icônes seules deviennent une devinette.
              title={replie ? item.label : undefined}
              className={`flex items-center rounded-xl py-2.5 text-sm transition ${
                replie ? "justify-center px-0" : "gap-3 px-3"
              } ${
                active
                  ? "bg-primary/10 text-primary-light"
                  : "text-foreground-muted hover:bg-surface-hover hover:text-foreground"
              }`}
            >
              <Icon name={item.icon} />
              {!replie && item.label}
            </Link>
          );
        })}
      </nav>

      <div className={`border-t border-outline-variant ${replie ? "p-2" : "p-4"}`}>
        <button
          onClick={onBasculer}
          title={replie ? "Déplier le menu" : "Replier le menu"}
          aria-label={replie ? "Déplier le menu" : "Replier le menu"}
          className={`mb-2 flex w-full items-center rounded-xl py-2 text-sm text-foreground-muted transition hover:bg-surface-hover hover:text-foreground ${
            replie ? "justify-center px-0" : "gap-2 px-3"
          }`}
        >
          <Icon name={replie ? "chevron_right" : "chevron_left"} />
          {!replie && "Replier"}
        </button>

        <div className={`mb-2 flex items-center ${replie ? "justify-center" : "gap-3"}`}>
          <div
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/20 font-mono text-xs text-primary-light"
            title={replie ? user.display_name : undefined}
          >
            {user.display_name.slice(0, 2).toUpperCase()}
          </div>
          {!replie && (
            <div className="min-w-0">
              <p className="truncate text-sm text-foreground">{user.display_name}</p>
              <p className="truncate font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
                {user.is_admin ? "Admin" : "Standard"}
              </p>
            </div>
          )}
        </div>

        <button
          onClick={onLogout}
          title={replie ? "Déconnexion" : undefined}
          className={`flex w-full items-center rounded-xl py-2 text-sm text-foreground-muted transition hover:bg-surface-hover hover:text-foreground ${
            replie ? "justify-center px-0" : "gap-2 px-3"
          }`}
        >
          <Icon name="logout" />
          {!replie && "Déconnexion"}
        </button>
      </div>
    </aside>
  );
}
