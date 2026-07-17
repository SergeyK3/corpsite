// FILE: corpsite-ui/app/directory/personnel/_components/PersonnelSubNav.tsx
"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import * as React from "react";

import { listImportBatches } from "../_lib/importApi.client";

const IMPORT_LIST_HREF = "/directory/personnel/import";

const BASE_ITEMS = [
  {
    href: "/directory/personnel/journal",
    title: "Кадровый журнал",
    prefixes: ["/directory/personnel/journal"],
  },
  {
    href: "/directory/personnel-applications",
    title: "Кадровые обращения",
    prefixes: ["/directory/personnel-applications"],
  },
  {
    href: "/directory/personnel/applicants",
    title: "Претенденты",
    prefixes: ["/directory/personnel/applicants"],
  },
  {
    href: "/directory/personnel/onboarding",
    title: "Адаптация",
    prefixes: ["/directory/personnel/onboarding"],
  },
  {
    href: "/directory/personnel/orders",
    title: "Приказы",
    prefixes: ["/directory/personnel/orders"],
  },
  {
    href: "/directory/personnel/documents",
    title: "Реестр документов",
    prefixes: ["/directory/personnel/documents"],
  },
  {
    href: "/directory/personnel/hr-change-events",
    title: "Изменения реестра",
    prefixes: ["/directory/personnel/hr-change-events"],
  },
  {
    href: "/directory/personnel/migration",
    title: "Миграция",
    prefixes: ["/directory/personnel/migration"],
  },
] as const;

type ImportNavItem =
  | {
      key: string;
      title: string;
      href: string;
      isActive: (pathname: string) => boolean;
    }
  | {
      key: string;
      title: string;
      hrefForBatch: (batchId: number) => string;
      isActive: (pathname: string, batchId: number | null, reviewMode: string) => boolean;
    };

const IMPORT_REVIEW_HREF = "/directory/personnel/import/review";

const IMPORT_ITEMS: ImportNavItem[] = [
  {
    key: "import-list",
    title: "Импорт / аналитика",
    href: IMPORT_LIST_HREF,
    isActive: (pathname: string) =>
      pathname === IMPORT_LIST_HREF ||
      pathname === `${IMPORT_LIST_HREF}/` ||
      pathname === `${IMPORT_LIST_HREF}/upload`,
  },
  {
    key: "import-normalized-review",
    title: "Проверка записей",
    href: IMPORT_REVIEW_HREF,
    isActive: (pathname: string) =>
      pathname === IMPORT_REVIEW_HREF || pathname.startsWith(`${IMPORT_REVIEW_HREF}/`),
  },
  {
    key: "import-analytics",
    title: "Аналитика",
    hrefForBatch: (batchId: number) => `/directory/personnel/import/${batchId}`,
    isActive: (pathname: string, batchId: number | null) =>
      batchId != null && pathname === `/directory/personnel/import/${batchId}`,
  },
  {
    key: "import-med-categories",
    title: "Мед. категории",
    hrefForBatch: (batchId: number) => `/directory/personnel/import/${batchId}/review?mode=personnel`,
    isActive: (pathname: string, batchId: number | null, reviewMode: string) => {
      if (batchId == null || reviewMode === "declaration" || reviewMode === "technical") return false;
      return isReviewSectionActive(pathname, batchId, reviewMode, "personnel");
    },
  },
  {
    key: "import-declarations",
    title: "Декларации",
    hrefForBatch: (batchId: number) => `/directory/personnel/import/${batchId}/review?mode=declaration`,
    isActive: (pathname: string, batchId: number | null, reviewMode: string) => {
      if (batchId == null) return false;
      return isReviewSectionActive(pathname, batchId, reviewMode, "declaration");
    },
  },
  {
    key: "import-technical",
    title: "Технические",
    hrefForBatch: (batchId: number) => `/directory/personnel/import/${batchId}/review?mode=technical`,
    isActive: (pathname: string, batchId: number | null, reviewMode: string) => {
      if (batchId == null) return false;
      return isReviewSectionActive(pathname, batchId, reviewMode, "technical");
    },
  },
];

function isBaseItemActive(pathname: string, prefixes: readonly string[], href: string): boolean {
  if (pathname === "/directory/personnel" || pathname === "/directory/personnel/") {
    return href === "/directory/personnel/journal";
  }
  return prefixes.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

function parseBatchIdFromPath(pathname: string): number | null {
  const match = pathname.match(/^\/directory\/personnel\/import\/(\d+)(?:\/|$)/);
  if (!match) return null;
  const batchId = Number(match[1]);
  return Number.isFinite(batchId) && batchId > 0 ? batchId : null;
}

function isReviewSectionActive(
  pathname: string,
  batchId: number,
  reviewMode: string,
  expectedMode: string
): boolean {
  if (reviewMode !== expectedMode) return false;
  const base = `/directory/personnel/import/${batchId}`;
  return pathname.startsWith(`${base}/review`) || pathname.startsWith(`${base}/rows`);
}

function resolveImportNavBatchId(pathname: string, latestBatchId: number | null): number | null {
  return parseBatchIdFromPath(pathname) ?? latestBatchId;
}

function tabClassName(active: boolean, disabled = false): string {
  if (disabled) {
    return "cursor-not-allowed rounded-lg bg-zinc-50 px-3 py-1.5 text-sm font-medium text-zinc-400 dark:bg-zinc-900/50 dark:text-zinc-600";
  }
  return [
    "rounded-lg px-3 py-1.5 text-sm font-medium transition",
    active
      ? "bg-blue-600 text-white"
      : "bg-zinc-100 text-zinc-800 hover:bg-zinc-200 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800",
  ].join(" ");
}

export default function PersonnelSubNav() {
  const pathname = usePathname() || "";
  const searchParams = useSearchParams();
  const reviewMode = searchParams.get("mode") || "personnel";
  const [latestBatchId, setLatestBatchId] = React.useState<number | null>(null);

  React.useEffect(() => {
    let cancelled = false;

    listImportBatches()
      .then((data) => {
        if (cancelled) return;
        const batchId = data.items[0]?.batch_id;
        setLatestBatchId(typeof batchId === "number" && batchId > 0 ? batchId : null);
      })
      .catch(() => {
        if (!cancelled) setLatestBatchId(null);
      });

    return () => {
      cancelled = true;
    };
  }, [pathname]);

  const navBatchId = resolveImportNavBatchId(pathname, latestBatchId);

  return (
    <nav className="flex flex-wrap gap-2">
      {BASE_ITEMS.map((item) => {
        const active = isBaseItemActive(pathname, item.prefixes, item.href);
        return (
          <Link key={item.href} href={item.href} className={tabClassName(active)}>
            {item.title}
          </Link>
        );
      })}

      {IMPORT_ITEMS.map((item) => {
        if ("href" in item) {
          return (
            <Link key={item.key} href={item.href} className={tabClassName(item.isActive(pathname))}>
              {item.title}
            </Link>
          );
        }

        const href = navBatchId != null ? item.hrefForBatch(navBatchId) : IMPORT_LIST_HREF;
        const active = navBatchId != null ? item.isActive(pathname, navBatchId, reviewMode) : false;
        const disabled = navBatchId == null;

        if (disabled) {
          return (
            <span key={item.key} className={tabClassName(false, true)} aria-disabled="true">
              {item.title}
            </span>
          );
        }

        return (
          <Link key={item.key} href={href} className={tabClassName(active)}>
            {item.title}
          </Link>
        );
      })}
    </nav>
  );
}
