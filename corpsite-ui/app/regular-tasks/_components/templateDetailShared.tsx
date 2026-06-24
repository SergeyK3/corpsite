import * as React from "react";

import { scheduleTypeLabel } from "@/lib/i18n";

export const TEMPLATE_FORM_ID = "regular-task-template-form";

export const SCHEDULE_TYPE_FORM_OPTIONS = [
  { value: "weekly", label: "Еженедельная" },
  { value: "monthly", label: "Ежемесячная" },
  { value: "yearly", label: "Ежегодная" },
] as const;

export function scheduleTypeFormLabel(code: string | null | undefined): string {
  const normalized = String(code ?? "").trim().toLowerCase();
  const match = SCHEDULE_TYPE_FORM_OPTIONS.find((option) => option.value === normalized);
  if (match) return match.label;
  return scheduleTypeLabel(code) || String(code ?? "").trim() || "—";
}

export function TemplateSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-5">
      <div className="mb-4">
        <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">{title}</h3>
        {description ? <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}

export function TemplateField({
  label,
  htmlFor,
  required,
  children,
}: {
  label: string;
  htmlFor?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={htmlFor} className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
        {label}
        {required ? <span className="text-red-400"> *</span> : null}
      </label>
      {children}
    </div>
  );
}

export function TemplateReadOnlyValue({ value }: { value: React.ReactNode }) {
  return (
    <div className="min-h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100/70 dark:bg-zinc-900/70 px-4 py-2.5 text-sm text-zinc-900 dark:text-zinc-50">
      {value ?? "—"}
    </div>
  );
}

export const templateFieldInputClassName =
  "h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400";

export const templateTextareaClassName =
  "resize-y rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-3 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400";
