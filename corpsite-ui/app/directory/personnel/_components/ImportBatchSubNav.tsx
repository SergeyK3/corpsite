"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { suffix: "", label: "Аналитика", match: (p: string, id: number) => p === `/directory/personnel/import/${id}` },
  {
    suffix: "/review",
    label: "Review",
    match: (p: string, id: number) => p.startsWith(`/directory/personnel/import/${id}/review`) || p.includes(`/import/${id}/rows`),
  },
  {
    suffix: "/training",
    label: "Образовательные профили",
    match: (p: string, id: number) => p.startsWith(`/directory/personnel/import/${id}/training`),
  },
] as const;

export default function ImportBatchSubNav({ batchId }: { batchId: number }) {
  const pathname = usePathname() || "";

  return (
    <nav className="mb-4 flex flex-wrap items-center gap-2 border-b border-zinc-200 pb-3 dark:border-zinc-800">
      <Link
        href="/directory/personnel/import"
        className="mr-2 text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
      >
        ← Импорты
      </Link>
      {TABS.map((tab) => {
        const href = `/directory/personnel/import/${batchId}${tab.suffix || ""}`;
        const active = tab.match(pathname, batchId);
        return (
          <Link
            key={tab.suffix || "analytics"}
            href={href}
            className={[
              "rounded-lg px-3 py-1.5 text-sm font-medium transition",
              active
                ? "bg-blue-600 text-white"
                : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900",
            ].join(" ")}
          >
            {tab.label}
          </Link>
        );
      })}
      <span className="ml-auto text-xs text-zinc-400">Batch #{batchId}</span>
    </nav>
  );
}
