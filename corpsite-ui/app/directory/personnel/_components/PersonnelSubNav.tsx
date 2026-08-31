// FILE: corpsite-ui/app/directory/personnel/_components/PersonnelSubNav.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { isPersonnelControlListPath } from "../_lib/personnelControlListNav";

const BASE_ITEMS = [
  { href: "/directory/personnel/journal", title: "Кадровый журнал", prefixes: ["/directory/personnel/journal"] },
  {
    href: "/directory/personnel/lk",
    title: "Личные карточки",
    prefixes: ["/directory/personnel/lk", "/directory/personnel/applicants"],
  },
  { href: "/directory/personnel/onboarding", title: "Адаптация", prefixes: ["/directory/personnel/onboarding"] },
  { href: "/directory/personnel/orders", title: "Приказы", prefixes: ["/directory/personnel/orders"] },
  {
    href: "/directory/personnel/documents",
    title: "Реестр документов",
    prefixes: ["/directory/personnel/documents"],
  },
  {
    href: "/directory/personnel/employment-verification",
    title: "Проверка биографии",
    prefixes: ["/directory/personnel/employment-verification"],
  },
] as const;

function isBaseItemActive(pathname: string, prefixes: readonly string[], href: string): boolean {
  if (pathname === "/directory/personnel" || pathname === "/directory/personnel/") {
    return href === "/directory/personnel/journal";
  }
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

function tabClassName(active: boolean): string {
  return [
    "rounded-lg px-3 py-1.5 text-sm font-medium transition",
    active
      ? "bg-blue-600 text-white"
      : "bg-zinc-100 text-zinc-800 hover:bg-zinc-200 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800",
  ].join(" ");
}

export default function PersonnelSubNav() {
  const pathname = usePathname() || "";
  const controlListActive = isPersonnelControlListPath(pathname);

  return (
    <nav aria-label="Навигация кадровых процессов" className="flex flex-wrap gap-2">
      {BASE_ITEMS.map((item) => {
        const active = isBaseItemActive(pathname, item.prefixes, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={tabClassName(active)}
            aria-current={active ? "page" : undefined}
          >
            {item.title}
          </Link>
        );
      })}
      <Link
        href="/directory/personnel/import"
        className={tabClassName(controlListActive)}
        aria-current={controlListActive ? "page" : undefined}
      >
        Контрольный список
      </Link>
    </nav>
  );
}
