// FILE: corpsite-ui/app/admin/system/_lib/personnelLifecycleLabels.ts

import type { ValidationCheck } from "./personnelLifecycleApi.client";

export const VALIDATION_CARD_CODES: Record<
  string,
  { title: string; description: string }
> = {
  duplicate_active_overrides: {
    title: "Дублирующиеся исключения",
    description: "Активные исключения с дублирующимся scope_key + field_path",
  },
  duplicate_active_assignments: {
    title: "Дублирующиеся назначения",
    description: "Активные назначения с дублирующимся person + assignment_key",
  },
  active_assignment_without_person: {
    title: "Назначения без персоны",
    description: "Активные назначения без связанной записи персоны",
  },
  personnel_events_stuck_detected: {
    title: "Застрявшие события",
    description: "События персонала, остающиеся в статусе detected для пары снимков",
  },
  outdated_effective_cache: {
    title: "Устаревший кэш",
    description: "Снимки, где число effective cache отстаёт от канонического roster",
  },
  persons_without_active_assignment: {
    title: "Персоны без назначения",
    description: "Активные персоны без активного назначения",
  },
};

export function formatDurationMs(ms?: number | null): string {
  if (ms == null || Number.isNaN(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  const mins = Math.floor(ms / 60_000);
  const secs = Math.round((ms % 60_000) / 1000);
  return `${mins}m ${secs}s`;
}

export function formatDurationBetween(
  started?: string | null,
  completed?: string | null,
): string {
  if (!started || !completed) return "—";
  const ms = new Date(completed).getTime() - new Date(started).getTime();
  if (Number.isNaN(ms) || ms < 0) return "—";
  return formatDurationMs(ms);
}

export function lifecycleStatusClass(status: string): string {
  const s = status.toLowerCase();
  if (s === "completed" || s === "success") {
    return "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200";
  }
  if (s === "failed" || s === "error") {
    return "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200";
  }
  if (s === "running" || s === "in_progress") {
    return "bg-blue-100 text-blue-900 dark:bg-blue-950 dark:text-blue-200";
  }
  return "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200";
}

export function overrideStatusClass(status: string): string {
  const s = status.toLowerCase();
  if (s === "active" || s === "approved") {
    return "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200";
  }
  if (s === "pending_approval" || s === "pending") {
    return "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200";
  }
  if (s === "rejected" || s === "revoked") {
    return "bg-red-100 text-red-900 dark:bg-red-950 dark:text-red-200";
  }
  return "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200";
}

export function validationSeverityClass(severity: string): string {
  const s = severity.toLowerCase();
  if (s === "error") return "border-red-300 dark:border-red-800";
  if (s === "warning") return "border-amber-300 dark:border-amber-800";
  return "border-emerald-300 dark:border-emerald-800";
}

export function findValidationCheck(
  checks: ValidationCheck[],
  code: string,
): ValidationCheck | undefined {
  return checks.find((c) => c.code === code);
}

export function canApproveOverride(status: string): boolean {
  return status.toLowerCase() === "pending_approval";
}

export function canRejectOverride(status: string): boolean {
  return status.toLowerCase() === "pending_approval";
}

export function canRevokeOverride(status: string): boolean {
  return status.toLowerCase() === "active";
}

export function canReconfirmOverride(status: string, staleFlag: boolean): boolean {
  return status.toLowerCase() === "active" && staleFlag;
}

export function effectiveOverrideValue(detail: {
  status: string;
  canonical_value?: unknown;
  override_value?: unknown;
}): unknown {
  if (detail.status.toLowerCase() === "active") return detail.override_value;
  return detail.canonical_value;
}
