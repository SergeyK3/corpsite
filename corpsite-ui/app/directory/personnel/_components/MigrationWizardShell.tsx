// PMF-4B — shared shell for Migration Wizard pages.
"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { HR_PROCESSES_NAV_HREF } from "@/lib/personnelNav";

type BreadcrumbSegment = {
  label: string;
  href?: string;
};

type MigrationWizardShellProps = {
  children: ReactNode;
  title: string;
  description?: string;
  breadcrumbTail?: BreadcrumbSegment[];
};

export default function MigrationWizardShell({
  children,
  title,
  description,
  breadcrumbTail = [],
}: MigrationWizardShellProps) {
  return (
    <div className="px-4 py-3">
      <header className="mb-4">
        <nav
          aria-label="Breadcrumb"
          className="flex flex-wrap items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400"
        >
          <Link href={HR_PROCESSES_NAV_HREF} className="hover:underline">
            Кадровые процессы
          </Link>
          <span aria-hidden="true">/</span>
          {breadcrumbTail.length === 0 ? (
            <span className="text-zinc-900 dark:text-zinc-100">Миграция</span>
          ) : (
            <>
              <Link href="/directory/personnel/migration" className="hover:underline">
                Миграция
              </Link>
              {breadcrumbTail.map((segment, index) => {
                const isLast = index === breadcrumbTail.length - 1;
                return (
                  <span key={`${segment.label}-${index}`} className="contents">
                    <span aria-hidden="true">/</span>
                    {segment.href && !isLast ? (
                      <Link href={segment.href} className="hover:underline">
                        {segment.label}
                      </Link>
                    ) : (
                      <span className="text-zinc-900 dark:text-zinc-100">{segment.label}</span>
                    )}
                  </span>
                );
              })}
            </>
          )}
        </nav>
        <h1 className="mt-2 text-xl font-semibold text-zinc-900 dark:text-zinc-100">{title}</h1>
        {description ? (
          <p className="mt-1 max-w-3xl text-sm text-zinc-600 dark:text-zinc-400">{description}</p>
        ) : null}
      </header>

      <div className="min-w-0 space-y-4">{children}</div>
    </div>
  );
}

export function MigrationInfoBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
      {message}
    </div>
  );
}

export function MigrationErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
      {message}
    </div>
  );
}

export function MigrationForbiddenPanel() {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-6 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
      <p className="font-medium">Недостаточно прав</p>
      <p className="mt-2">
        Перенос данных в кадровую карточку доступен только уполномоченным HR-операторам. Если вам нужен
        доступ, обратитесь к системному администратору.
      </p>
    </div>
  );
}

export function MigrationLoadingPanel({ label = "Загрузка…" }: { label?: string }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-4 py-8 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950">
      {label}
    </div>
  );
}

export function MigrationEmptyPanel({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-xl border border-dashed border-zinc-300 bg-zinc-50 px-4 py-8 text-center dark:border-zinc-700 dark:bg-zinc-900/40">
      <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{title}</p>
      <p className="mt-2 text-sm text-zinc-500">{description}</p>
    </div>
  );
}
