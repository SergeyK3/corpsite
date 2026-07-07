"use client";

import * as React from "react";

export type EmployeeImportCardSectionDef = {
  id: string;
  title: string;
};

export const EMPLOYEE_IMPORT_CARD_SECTIONS: EmployeeImportCardSectionDef[] = [
  { id: "assignment", title: "Назначение" },
  { id: "hr-contour", title: "Кадровый контур" },
  { id: "access", title: "Доступ" },
  { id: "history", title: "История" },
];

type SectionProps = {
  id: string;
  title: string;
  description: string;
  status?: React.ReactNode;
  actions?: React.ReactNode;
  footer?: React.ReactNode;
  children: React.ReactNode;
};

export function EmployeeImportCardSection({
  id,
  title,
  description,
  status,
  actions,
  footer,
  children,
}: SectionProps) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-heading`}
      className="scroll-mt-24 rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950"
    >
      <div className="border-b border-zinc-100 px-4 py-3 dark:border-zinc-800 sm:px-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 id={`${id}-heading`} className="text-base font-semibold text-zinc-900 dark:text-zinc-50">
                {title}
              </h2>
              {status ? <div className="flex flex-wrap items-center gap-1.5">{status}</div> : null}
            </div>
            <p className="mt-1 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">{description}</p>
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      </div>

      <div className="px-4 py-4 sm:px-5">{children}</div>

      {footer ? (
        <div className="border-t border-dashed border-zinc-200 px-4 py-2 dark:border-zinc-800 sm:px-5">
          {footer}
        </div>
      ) : null}
    </section>
  );
}

type NavProps = {
  className?: string;
};

export function EmployeeImportCardSectionNav({ className }: NavProps) {
  function scrollToSection(sectionId: string) {
    document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <nav
      aria-label="Разделы карточки сотрудника"
      className={[
        "sticky top-0 z-[1] -mx-4 mb-5 border-b border-zinc-200 bg-white/95 px-4 py-2 backdrop-blur-sm dark:border-zinc-800 dark:bg-zinc-950/95 sm:-mx-6 sm:px-6",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="flex flex-wrap gap-2">
        {EMPLOYEE_IMPORT_CARD_SECTIONS.map((section) => (
          <button
            key={section.id}
            type="button"
            onClick={() => scrollToSection(section.id)}
            className="rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-xs font-medium text-zinc-700 transition hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
          >
            {section.title}
          </button>
        ))}
      </div>
    </nav>
  );
}

export function EmployeeImportCardSectionPlaceholder({
  label,
  hint = "Раздел будет добавлен позже.",
}: {
  label: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-dashed border-zinc-200 bg-zinc-50/80 px-3 py-2 text-xs text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900/40 dark:text-zinc-400">
      <span className="font-medium text-zinc-600 dark:text-zinc-300">{label}</span>
      <span className="mx-1">·</span>
      {hint}
    </div>
  );
}
