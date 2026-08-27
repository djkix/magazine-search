"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Icon from "@/components/ui/Icon";
import type { User } from "@/lib/types";

export default function BottomNav({ user }: { user: User }) {
  const pathname = usePathname();
  const items = [
    { href: "/", label: "Recherche", icon: "search" },
    { href: "/library", label: "Bibliothèque", icon: "collections_bookmark" },
    { href: "/articles", label: "Sommaires", icon: "toc" },
    ...(user.is_admin ? [{ href: "/admin", label: "Admin", icon: "admin_panel_settings" }] : []),
  ];

  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-outline-variant bg-surface/95 backdrop-blur-md lg:hidden">
      {items.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[11px] ${
              active ? "text-primary-light" : "text-foreground-muted"
            }`}
          >
            <Icon name={item.icon} />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
