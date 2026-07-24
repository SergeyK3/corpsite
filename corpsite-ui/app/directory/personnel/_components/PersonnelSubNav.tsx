// FILE: corpsite-ui/app/directory/personnel/_components/PersonnelSubNav.tsx
"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import * as React from "react";

import { listImportBatches } from "../_lib/importApi.client";
import {
  buildImportReviewModeHref,
  IMPORT_REVIEW_MODE_TABS,
  isImportReviewModeNavActive,
} from "../_lib/importReviewNav";

const IMPORT_LIST_HREF = "/directory/personnel/import";

const BASE_ITEMS = [
  {
    href: "/directory/personnel/journal",
    title: "Кадровый журнал",
    prefixes: ["/directory/personnel/journal"],
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
    href: "/directory/personnel/employment-verification",
    title: "Проверка биографии",
    prefixes: ["/directory/personnel/employment-verification"],
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
      isActive: (pathname: string, batchId: number | null) => boolean;
    };

const IMPORT_REVIEW_HREF = "/directory/personnel/import/review";

const IMPORT_ITEMS: ImportNavItem[] = [
  {
    key: "import-list",
    title: "Импорт",
    href: IMPORT_LIST_HREF,
    isActive: (pathname: string) =>
      pathname === IMPORT_LIST_HREF ||
      pathname === `${IMPORT_LIST_HREF}/` ||
      pathname === `${IMPORT_LIST_HREF}/upload` ||
      pathname === "/directory/personnel/baselines" ||
      pathname.startsWith("/directory/personnel/baselines/") ||
      pathname.startsWith("/directory/personnel/monthly-references/"),
  },
  {
    key: "import-analytics",
    title: "Аналитика",
    hrefForBatch: (batchId: number) => `/directory/personnel/import/${batchId}`,
    isActive: (pathname: string, batchId: number | null) =>
      batchId != null && pathname === `/directory/personnel/import/${batchId}`,
  },
  {
    key: "import-normalized-review",
    title: "Проверка записей",
    href: IMPORT_REVIEW_HREF,
    isActive: (pathname: string) =>
      pathname === IMPORT_REVIEW_HREF || pathname.startsWith(`${IMPORT_REVIEW_HREF}/`),
  },
  {
    key: "import-hr-change-events",
    title: "Изменения реестра",
    href: "/directory/personnel/hr-change-events",
    isActive: (pathname: string) =>
      pathname === "/directory/personnel/hr-change-events" ||
      pathname.startsWith("/directory/personnel/hr-change-events/"),
  },
  {
    key: "import-migration",
    title: "Миграция",
    href: "/directory/personnel/migration",
    isActive: (pathname: string) =>
      pathname === "/directory/personnel/migration" ||
      pathname.startsWith("/directory/personnel/migration/"),
  },
  ...IMPORT_REVIEW_MODE_TABS.map((tab) => ({
    key: tab.key,
    title: tab.title,
    hrefForBatch: (batchId: number) => buildImportReviewModeHref(batchId, tab.mode),
    isActive: (pathname: string, batchId: number | null) =>
      isImportReviewModeNavActive(pathname, tab.mode, batchId, new URLSearchParams()),
  })),
  {
    key: "import-training",
    title: "Обучение",
    hrefForBatch: (batchId: number) => `/directory/personnel/import/${batchId}/training`,
    isActive: (pathname: string, batchId: number | null) =>
      batchId != null && pathname.startsWith(`/directory/personnel/import/${batchId}/training`),
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

function resolveImportNavBatchId(pathname: string, latestBatchId: number | null): number | null {
  return parseBatchIdFromPath(pathname) ?? latestBatchId;
}

function isImportBatchNavItemActive(
  item: Extract<ImportNavItem, { hrefForBatch: (batchId: number) => string }>,
  pathname: string,
  navBatchId: number | null,
  searchParams: Pick<URLSearchParams, "get">,
): boolean {
  if (navBatchId == null) return false;
  const reviewTab = IMPORT_REVIEW_MODE_TABS.find((tab) => tab.key === item.key);
  if (reviewTab) {
    return isImportReviewModeNavActive(pathname, reviewTab.mode, navBatchId, searchParams);
  }
  return item.isActive(pathname, navBatchId);
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
        const active = isImportBatchNavItemActive(item, pathname, navBatchId, searchParams);
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
