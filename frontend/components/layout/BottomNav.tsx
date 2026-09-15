"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Icon from "@/components/ui/Icon";
import { NAV_ITEMS } from "./Sidebar";
import type { User } from "@/lib/types";

export default function BottomNav({ user }: { user: User }) {
  const pathname = usePathname();

  // Même source que la barre latérale. Cette liste était auparavant recopiée,
  // et la recopie avait déjà divergé : « Thématiques » n'existait que sur
  // ordinateur, rendant la navigation par sujet inaccessible au téléphone.
  const items = user.is_admin
    ? [...NAV_ITEMS, { href: "/admin", label: "Admin", icon: "admin_panel_settings" }]
    : NAV_ITEMS;

  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-outline-variant bg-surface/95 backdrop-blur-md lg:hidden">
      {items.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            title={item.label}
            // min-w-0 et truncate sont indispensables ici : à cinq ou six
            // entrées sur un écran de 375 px, « Bibliothèque » déborderait et
            // déformerait toute la barre.
            className={`flex min-w-0 flex-1 flex-col items-center gap-0.5 px-1 py-2.5 text-[11px] ${
              active ? "text-primary-light" : "text-foreground-muted"
            }`}
          >
            <Icon name={item.icon} />
            <span className="w-full truncate text-center">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
