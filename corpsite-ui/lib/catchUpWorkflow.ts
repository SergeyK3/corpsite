// FILE: corpsite-ui/lib/catchUpWorkflow.ts

import type { CatchUpPreset, CatchUpRegularTasksParams } from "./api";
import {
  fmtDate,
  itemOutcomeLabel,
  resolveItemOccurrenceDate,
  resolveItemOutcome,
  roleLabel,
  type RegularTaskRunItemRow,
} from "./regularTaskRunJournal";

export type CatchUpScheduleType = "weekly" | "monthly" | "yearly";

export type CatchUpReviewRow = {
  item_id: number;
  template_label: string;
  report_code: string;
  executor_label: string;
  period_label: string;
  due_date_label: string;
  occurrence_date_label: string;
  reason_label: string;
  title_final: string;
};

export function resolveDefaultScheduleType(preset: CatchUpPreset): CatchUpScheduleType {
  if (preset === "past_month") return "monthly";
  if (preset === "past_week") return "weekly";
  return "weekly";
}

export function pastWeekPresetHint(): string {
  return "Будет использована последняя среда в окне [today−7; today−1]. Период отчётности = 7 дней до этой даты.";
}

export function formatReportingPeriodRange(
  periodStart?: string | null,
  periodEnd?: string | null,
): string | null {
  const start = String(periodStart ?? "").trim();
  const end = String(periodEnd ?? "").trim();
  if (!start || !end) return null;
  return `${fmtDate(start)}–${fmtDate(end)}`;
}

export function resolveAggregatePeriodFromItems(
  items: readonly RegularTaskRunItemRow[],
): string | null {
  for (const item of items) {
    const label = formatReportingPeriodRange(item.meta?.period_start, item.meta?.period_end);
    if (label) return label;
  }
  for (const item of items) {
    const suffix = String(item.meta?.title_suffix ?? "").trim();
    if (suffix) return suffix;
  }
  return null;
}

export function resolveAggregateOccurrenceDate(
  items: readonly RegularTaskRunItemRow[],
  runForDate?: string | null,
): string | null {
  for (const item of items) {
    const occ = resolveItemOccurrenceDate(item);
    if (occ) return occ;
  }
  const fallback = String(runForDate ?? "").trim();
  return fallback || null;
}

export function catchUpItemReasonLabel(
  item: RegularTaskRunItemRow,
  options: { isDryRunPreview: boolean },
): string {
  const { isDryRunPreview } = options;
  if (isDryRunPreview) {
    return "Пробный прогон (dry_run)";
  }

  switch (resolveItemOutcome(item)) {
    case "created":
      return "Создание (create)";
    case "dedup":
      return "Дедупликация (dedup)";
    case "error":
      return "Ошибка";
    case "skip":
      return "Пропуск";
    default:
      return itemOutcomeLabel(item);
  }
}

export function buildCatchUpReviewRow(
  item: RegularTaskRunItemRow,
  options: { isDryRunPreview: boolean },
): CatchUpReviewRow {
  const templateTitle = String(item.meta?.template_title ?? "").trim();
  const templateLabel = templateTitle
    ? `${templateTitle} (#${item.regular_task_id})`
    : `Шаблон №${item.regular_task_id}`;

  const periodLabel =
    formatReportingPeriodRange(item.meta?.period_start, item.meta?.period_end) ??
    (String(item.meta?.title_suffix ?? "").trim() || "—");

  const titleFinal = String(item.meta?.title_final ?? item.meta?.task_title ?? "").trim() || "—";
  const reportCode = String(item.meta?.report_code ?? "").trim() || "—";
  const dueRaw = String(item.meta?.due_date ?? "").trim();
  const occurrenceRaw = resolveItemOccurrenceDate(item);

  return {
    item_id: item.item_id,
    template_label: templateLabel,
    report_code: reportCode,
    executor_label: roleLabel(item),
    period_label: periodLabel,
    due_date_label: dueRaw ? fmtDate(dueRaw) : "—",
    occurrence_date_label: occurrenceRaw ? fmtDate(occurrenceRaw) : "—",
    reason_label: catchUpItemReasonLabel(item, options),
    title_final: titleFinal,
  };
}

export function buildCatchUpReviewRows(
  items: readonly RegularTaskRunItemRow[],
  options: { isDryRunPreview: boolean },
): CatchUpReviewRow[] {
  return [...items]
    .sort((a, b) => a.item_id - b.item_id)
    .map((item) => buildCatchUpReviewRow(item, options));
}

export type CatchUpFormState = {
  preset: CatchUpPreset;
  manualDate: string;
  scheduleType: CatchUpScheduleType;
  orgGroupId: number | null;
  orgUnitId: number | null;
  executorRoleId: number | null;
};

export function buildCatchUpPayload(
  form: CatchUpFormState,
  dryRun: boolean,
): CatchUpRegularTasksParams {
  const payload: CatchUpRegularTasksParams = {
    dry_run: dryRun,
    preset: form.preset,
    schedule_type: form.scheduleType,
  };

  if (form.preset === "manual") {
    payload.run_for_date = form.manualDate.trim();
  }
  if (form.orgGroupId != null) {
    payload.org_group_id = form.orgGroupId;
  }
  if (form.orgUnitId != null) {
    payload.org_unit_id = form.orgUnitId;
  }
  if (form.executorRoleId != null) {
    payload.executor_role_id = form.executorRoleId;
  }

  return payload;
}

export function validateCatchUpForm(form: CatchUpFormState): string | null {
  if (form.preset === "manual") {
    const manualDate = form.manualDate.trim();
    if (!manualDate) return "Укажите дату для ручного пресета.";
    if (Number.isNaN(Date.parse(manualDate))) {
      return "Некорректная дата (ожидается YYYY-MM-DD).";
    }
  }
  return null;
}

export function payloadsEquivalent(
  a: CatchUpRegularTasksParams,
  b: CatchUpRegularTasksParams,
): boolean {
  const normalize = (p: CatchUpRegularTasksParams) =>
    JSON.stringify({
      preset: p.preset,
      run_for_date: p.run_for_date ?? null,
      schedule_type: p.schedule_type ?? null,
      org_group_id: p.org_group_id ?? null,
      org_unit_id: p.org_unit_id ?? null,
      executor_role_id: p.executor_role_id ?? null,
    });

  return normalize(a) === normalize(b);
}
