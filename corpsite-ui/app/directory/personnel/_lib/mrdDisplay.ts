/** Display helpers for Monthly Reference Dataset UI (WP-MRD-004). */
import { formatPersonnelDate } from "@/lib/personnelDateFormat";
import type { MonthlyReferenceSummary } from "./mrdApi.client";

export type MrdForkMode = "version" | "period";

export function formatMrdStatusLabel(status: string): string {
  if (status === "ACTIVE") return "действующая";
  if (status === "CLOSED") return "закрыта";
  return status;
}

/** Статус версии в журнале эталонов — по фактическому полю status. */
export function formatMrdJournalStatusLabel(
  row: Pick<MonthlyReferenceSummary, "status" | "is_active_for_period">,
): string {
  if (row.status === "ACTIVE") return "Действующий";
  if (row.status === "CLOSED") return "Архивный";
  return row.status;
}

export function formatMrdJournalMissingStatusLabel(): string {
  return "Не создан";
}

export function mrdJournalMissingStatusClassName(): string {
  return "inline-flex rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400";
}

export function mrdJournalStatusClassName(
  row: Pick<MonthlyReferenceSummary, "status" | "is_active_for_period">,
): string {
  const active = row.status === "ACTIVE";
  return active
    ? "inline-flex rounded-full border border-green-200 bg-green-50 px-2 py-0.5 text-xs font-medium text-green-900 dark:border-green-900 dark:bg-green-950 dark:text-green-100"
    : "inline-flex rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs font-medium text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300";
}

export function formatMrdReportPeriod(value: string | null | undefined): string {
  return formatPersonnelDate(value, { precision: "month" });
}

export function formatMrdVersionLabel(row: Pick<MonthlyReferenceSummary, "report_period" | "version" | "status">): string {
  return `${formatMrdReportPeriod(row.report_period)}, версия ${row.version} (${formatMrdStatusLabel(row.status)})`;
}

export function formatMrdPeriodHeadline(reportPeriod: string): string {
  return `Период ${formatMrdReportPeriod(reportPeriod)}`;
}

const RUSSIAN_MONTHS = [
  "январь",
  "февраль",
  "март",
  "апрель",
  "май",
  "июнь",
  "июль",
  "август",
  "сентябрь",
  "октябрь",
  "ноябрь",
  "декабрь",
] as const;

/** «Эталон кадровых данных за июль 2026» */
export function formatEtalonPeriodTitle(reportPeriod: string | null | undefined): string {
  if (!reportPeriod) return "Эталон кадровых данных";
  const raw = reportPeriod.slice(0, 10);
  const match = /^(\d{4})-(\d{2})/.exec(raw);
  if (!match) return "Эталон кадровых данных";
  const year = match[1];
  const monthIndex = Number(match[2]) - 1;
  const monthName = RUSSIAN_MONTHS[monthIndex] ?? match[2];
  return `Эталон кадровых данных за ${monthName} ${year}`;
}

export function formatMrdActiveHeadline(active: MonthlyReferenceSummary | null | undefined): string {
  if (!active) return "Для периода ещё не создан действующий эталон";
  return `Действующий эталон: ${formatMrdReportPeriod(active.report_period)}`;
}

export function groupMrdSourcesByPeriod(items: MonthlyReferenceSummary[]): Array<{
  reportPeriod: string;
  items: MonthlyReferenceSummary[];
}> {
  const map = new Map<string, MonthlyReferenceSummary[]>();
  for (const item of items) {
    const key = item.report_period.slice(0, 10);
    const bucket = map.get(key) ?? [];
    bucket.push(item);
    map.set(key, bucket);
  }
  return [...map.entries()]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([reportPeriod, groupedItems]) => ({
      reportPeriod,
      items: groupedItems.sort((a, b) => b.version - a.version),
    }));
}

export function validateForkPeriodTarget(
  targetReportPeriod: string,
  existingPeriods: Set<string>,
): string | null {
  const normalized = targetReportPeriod.trim();
  if (!/^\d{4}-\d{2}$/.test(normalized) && !/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
    return "Укажите период в формате ГГГГ-ММ.";
  }
  const key = normalized.length === 7 ? `${normalized}-01` : normalized;
  if (existingPeriods.has(key)) {
    return "Для выбранного периода уже существует эталон.";
  }
  return null;
}

export function buildForkVersionWarnings(
  source: MonthlyReferenceSummary | null,
  active: MonthlyReferenceSummary | null,
): string[] {
  const warnings: string[] = [];
  if (!source) return warnings;
  if (active && active.mrd_id !== source.mrd_id) {
    warnings.push(
      `Сейчас действует версия ${active.version}; она будет закрыта. Новая версия будет создана на основе выбранной версии ${source.version}.`,
    );
  }
  warnings.push(
    "Будут скопированы только подтверждённые записи. Обнаруженные различия и журнал подтверждённых изменений не переносятся.",
  );
  return warnings;
}

export function buildForkPeriodWarnings(source: MonthlyReferenceSummary | null): string[] {
  const warnings = [
    "Будет создан рабочий эталон для следующего отчётного периода на основе действующего эталона исходного периода.",
    "Исходный период не изменяется.",
    "Копируются только подтверждённые записи.",
  ];
  if (source) {
    warnings.push(`Исходный период: ${formatMrdReportPeriod(source.report_period)}.`);
  }
  return warnings;
}
