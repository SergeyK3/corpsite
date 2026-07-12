"use client";

import type { ValidationIssue, ValidationResult } from "../_lib/types";
import { validationSeverityLabel } from "../_lib/status";

type Props = {
  title: string;
  validation: ValidationResult | null | undefined;
  onRevalidate?: () => void;
  revalidateDisabled?: boolean;
  revalidatePending?: boolean;
};

function validationSummary(validation: ValidationResult | null | undefined): string {
  if (!validation) return "Нет данных";
  if (validation.has_errors) return "Требуется исправление";
  if (validation.has_warnings) return "Есть предупреждения";
  return "Готово";
}

function groupIssues(issues: ValidationIssue[]) {
  const order = ["ERROR", "WARNING", "INFO"] as const;
  const groups: Record<string, ValidationIssue[]> = { ERROR: [], WARNING: [], INFO: [] };
  for (const issue of issues) {
    const key = issue.severity.toUpperCase();
    if (key in groups) groups[key].push(issue);
    else groups.INFO.push(issue);
  }
  return order.filter((k) => groups[k].length > 0).map((k) => ({ severity: k, items: groups[k] }));
}

function issueRow(issue: ValidationIssue) {
  const severity = issue.severity.toUpperCase();
  const tone =
    severity === "ERROR"
      ? "border-red-200 bg-red-50 text-red-900"
      : severity === "WARNING"
        ? "border-amber-200 bg-amber-50 text-amber-900"
        : "border-blue-200 bg-blue-50 text-blue-900";

  return (
    <li key={`${issue.code}-${issue.field_path ?? ""}-${issue.message}`} className={`rounded-lg border px-3 py-2 text-sm ${tone}`}>
      <div>{issue.message}</div>
      <div className="mt-1 text-xs opacity-75">
        {issue.code}
        {issue.field_path ? ` · ${issue.field_path}` : ""}
      </div>
    </li>
  );
}

export default function ValidationPanel({
  title,
  validation,
  onRevalidate,
  revalidateDisabled,
  revalidatePending,
}: Props) {
  const issues = validation?.issues ?? [];
  const errorCount = issues.filter((i) => i.severity.toUpperCase() === "ERROR").length;
  const warningCount = issues.filter((i) => i.severity.toUpperCase() === "WARNING").length;
  const groups = groupIssues(issues);

  return (
    <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800" data-testid="validation-panel">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          <p className="text-xs text-zinc-500" data-testid="validation-summary">
            {validationSummary(validation)}
            {errorCount ? ` · blockers: ${errorCount}` : ""}
            {warningCount ? ` · warnings: ${warningCount}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {onRevalidate ? (
            <button
              type="button"
              disabled={revalidateDisabled || revalidatePending}
              onClick={onRevalidate}
              className="rounded-md border border-zinc-300 px-2 py-1 text-xs disabled:opacity-50 dark:border-zinc-600"
            >
              {revalidatePending ? "Проверка…" : "Повторить проверку"}
            </button>
          ) : null}
        </div>
      </div>
      {!issues.length ? (
        <p className="text-sm text-zinc-500" data-testid="validation-empty">
          Замечаний нет
        </p>
      ) : (
        <div className="space-y-4" data-testid="validation-issues">
          {groups.map((group) => (
            <div key={group.severity} data-testid={`validation-group-${group.severity}`}>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                {validationSeverityLabel(group.severity)} ({group.items.length})
              </h4>
              <ul className="space-y-2">{group.items.map(issueRow)}</ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
