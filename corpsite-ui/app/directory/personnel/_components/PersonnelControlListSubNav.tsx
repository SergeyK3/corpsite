"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { useCurrentUser } from "@/lib/currentUser";

import { listImportBatches } from "../_lib/importApi.client";
import { buildImportReviewModeHref } from "../_lib/importReviewNav";
import {
  isPersonnelControlListPath,
  parsePersonnelImportBatchId,
  resolvePersonnelControlListSection,
  type PersonnelControlListSection,
} from "../_lib/personnelControlListNav";

const IMPORT_LIST_HREF = "/directory/personnel/import";

type ControlListNavItem = {
  key: PersonnelControlListSection;
  title: string;
  href: (batchId: number | null) => string;
  requiresBatch?: boolean;
  requiresExportPermission?: boolean;
};

const CONTROL_LIST_ITEMS: ControlListNavItem[] = [
  { key: "upload", title: "Загрузка", href: () => IMPORT_LIST_HREF },
  {
    key: "analytics",
    title: "Аналитика",
    href: (batchId) => (batchId == null ? IMPORT_LIST_HREF : `${IMPORT_LIST_HREF}/${batchId}`),
    requiresBatch: true,
  },
  { key: "review", title: "Проверка записей", href: () => "/directory/personnel/import/review" },
  { key: "changes", title: "Изменения реестра", href: () => "/directory/personnel/hr-change-events" },
  { key: "migration", title: "Миграция", href: () => "/directory/personnel/migration" },
  {
    key: "medical",
    title: "Мед. категории",
    href: (batchId) =>
      batchId == null ? IMPORT_LIST_HREF : buildImportReviewModeHref(batchId, "personnel"),
    requiresBatch: true,
  },
  {
    key: "export",
    title: "Экспорт",
    href: () => "/directory/personnel/control-list/export",
    requiresExportPermission: true,
  },
];

function itemClassName(active: boolean, disabled: boolean): string {
  if (disabled) {
    return "cursor-not-allowed rounded-md px-3 py-1.5 text-sm font-medium text-zinc-400 dark:text-zinc-600";
  }
  return [
    "rounded-md px-3 py-1.5 text-sm font-medium transition",
    active
      ? "bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-200 dark:bg-blue-950/50 dark:text-blue-300 dark:ring-blue-900"
      : "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-900",
  ].join(" ");
}

export default function PersonnelControlListSubNav() {
  const me = useCurrentUser();
  const pathname = usePathname() || "";
  const visible = isPersonnelControlListPath(pathname);
  const [latestBatchId, setLatestBatchId] = React.useState<number | null>(null);

  React.useEffect(() => {
    if (!visible) return;
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
  }, [visible]);

  if (!visible) return null;

  const currentSection = resolvePersonnelControlListSection(pathname);
  const batchId = parsePersonnelImportBatchId(pathname) ?? latestBatchId;

  return (
    <div className="mt-3 border-t border-zinc-200 pt-3 dark:border-zinc-800">
      <nav aria-label="Разделы контрольного списка" className="flex flex-wrap gap-1.5">
        {CONTROL_LIST_ITEMS.map((item) => {
          if (item.requiresExportPermission && me?.has_control_list_export !== true) {
            return null;
          }
          const disabled = item.requiresBatch === true && batchId == null;
          const active = currentSection === item.key;
          if (disabled) {
            return (
              <span key={item.key} aria-disabled="true" className={itemClassName(false, true)}>
                {item.title}
              </span>
            );
          }
          return (
            <Link
              key={item.key}
              href={item.href(batchId)}
              className={itemClassName(active, false)}
              aria-current={active ? "page" : undefined}
            >
              {item.title}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
