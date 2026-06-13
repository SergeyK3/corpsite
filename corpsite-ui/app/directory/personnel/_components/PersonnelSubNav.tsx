// FILE: corpsite-ui/app/directory/personnel/_components/PersonnelSubNav.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  { href: "/directory/personnel", title: "Сотрудники", prefixes: ["/directory/personnel"] },
  {
    href: "/directory/personnel/journal",
    title: "Кадровый журнал",
    prefixes: ["/directory/personnel/journal"],
  },
  {
    href: "/directory/personnel/documents",
    title: "Профессиональные документы",
    prefixes: ["/directory/personnel/documents"],
  },
] as const;

function isActive(pathname: string, prefixes: readonly string[], href: string): boolean {
  if (href === "/directory/personnel") {
    return pathname === href || pathname === "/directory/personnel/";
  }
  return prefixes.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export default function PersonnelSubNav() {
  const pathname = usePathname() || "";

  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-zinc-200 pb-3 dark:border-zinc-800">
      {ITEMS.map((item) => {
        const active = isActive(pathname, item.prefixes, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={[
              "rounded-lg px-3 py-1.5 text-sm font-medium transition",
              active
                ? "bg-blue-600 text-white"
                : "bg-zinc-100 text-zinc-800 hover:bg-zinc-200 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800",
            ].join(" ")}
          >
            {item.title}
          </Link>
        );
      })}
    </nav>
  );
}
