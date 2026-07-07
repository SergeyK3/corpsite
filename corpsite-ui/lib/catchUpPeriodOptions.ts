// FILE: corpsite-ui/lib/catchUpPeriodOptions.ts

import type { CatchUpPreset } from "./api";
import type { CatchUpScheduleType } from "./catchUpWorkflow";

export type CatchUpPeriodOption = {
  key: string;
  label: string;
  preset: CatchUpPreset;
  /** YYYY-MM-DD when preset=manual; empty for past_week / past_month shortcuts */
  manualDate: string;
};

const MONTH_NAMES_RU = [
  "Январь",
  "Февраль",
  "Март",
  "Апрель",
  "Май",
  "Июнь",
  "Июль",
  "Август",
  "Сентябрь",
  "Октябрь",
  "Ноябрь",
  "Декабрь",
] as const;

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

export function toIsoDateLocal(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

export function addDaysLocal(d: Date, days: number): Date {
  const next = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  next.setDate(next.getDate() + days);
  return next;
}

function firstDayOfMonthLocal(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function isoWeekdayLocal(d: Date): number {
  const day = d.getDay();
  return day === 0 ? 7 : day;
}

/** Mirrors backend resolve_catch_up_run_for_date for preset=past_week. */
export function resolvePastWeekRunForDate(today: Date): Date {
  const end = addDaysLocal(today, -1);
  const start = addDaysLocal(today, -7);
  let lastWed: Date | null = null;
  for (let cursor = start; cursor <= end; cursor = addDaysLocal(cursor, 1)) {
    if (isoWeekdayLocal(cursor) === 3) {
      lastWed = cursor;
    }
  }
  if (lastWed) return lastWed;

  let fallback = addDaysLocal(today, -1);
  while (isoWeekdayLocal(fallback) !== 3) {
    fallback = addDaysLocal(fallback, -1);
  }
  return fallback;
}

/** Mirrors backend _prev_month_period_bounds. */
export function prevMonthPeriodBounds(forDate: Date): { start: Date; end: Date } {
  const firstCur = firstDayOfMonthLocal(forDate);
  const lastPrev = addDaysLocal(firstCur, -1);
  const start = firstDayOfMonthLocal(lastPrev);
  const end = new Date(lastPrev.getFullYear(), lastPrev.getMonth(), lastPrev.getDate());
  return { start, end };
}

/** Mirrors backend _prev_week_period_bounds_simple. */
export function prevWeekPeriodBounds(forDate: Date): { start: Date; end: Date } {
  const end = addDaysLocal(forDate, -1);
  const start = addDaysLocal(forDate, -7);
  return { start, end };
}

/** Mirrors backend _prev_year_period_bounds reporting year label. */
export function prevYearReportingYear(forDate: Date): number {
  return forDate.getFullYear() - 1;
}

export function formatWeekRangeLabel(start: Date, end: Date): string {
  const sameYear = start.getFullYear() === end.getFullYear();
  const fmt = (d: Date, withYear: boolean) =>
    withYear
      ? `${pad2(d.getDate())}.${pad2(d.getMonth() + 1)}.${d.getFullYear()}`
      : `${pad2(d.getDate())}.${pad2(d.getMonth() + 1)}`;
  if (sameYear) {
    return `${fmt(start, false)}–${fmt(end, true)}`;
  }
  return `${fmt(start, true)}–${fmt(end, true)}`;
}

export function formatMonthYearLabel(d: Date): string {
  const month = MONTH_NAMES_RU[d.getMonth()] ?? pad2(d.getMonth() + 1);
  return `${month} ${d.getFullYear()}`;
}

function buildWeeklyPeriodOptions(today: Date, count: number): CatchUpPeriodOption[] {
  const anchor = resolvePastWeekRunForDate(today);
  const options: CatchUpPeriodOption[] = [];

  for (let i = 0; i < count; i += 1) {
    const runForDate = addDaysLocal(anchor, -7 * i);
    const { start, end } = prevWeekPeriodBounds(runForDate);
    const manualDate = toIsoDateLocal(runForDate);
    options.push({
      key: `weekly:${manualDate}`,
      label: formatWeekRangeLabel(start, end),
      preset: i === 0 ? "past_week" : "manual",
      manualDate: i === 0 ? "" : manualDate,
    });
  }

  return options;
}

function buildMonthlyPeriodOptions(today: Date, count: number): CatchUpPeriodOption[] {
  const firstCur = firstDayOfMonthLocal(today);
  const lastPrev = addDaysLocal(firstCur, -1);
  const anchor = firstDayOfMonthLocal(lastPrev);
  const options: CatchUpPeriodOption[] = [];

  for (let i = 0; i < count; i += 1) {
    const runForDate = new Date(anchor.getFullYear(), anchor.getMonth() - i, 1);
    const manualDate = toIsoDateLocal(runForDate);
    options.push({
      key: `monthly:${manualDate}`,
      label: formatMonthYearLabel(runForDate),
      preset: i === 0 ? "past_month" : "manual",
      manualDate: i === 0 ? "" : manualDate,
    });
  }

  return options;
}

function buildYearlyPeriodOptions(today: Date, count: number): CatchUpPeriodOption[] {
  const options: CatchUpPeriodOption[] = [];
  const currentYear = today.getFullYear();

  for (let i = 1; i <= count; i += 1) {
    const reportingYear = currentYear - i;
    const runForDate = new Date(reportingYear + 1, 0, 1);
    const manualDate = toIsoDateLocal(runForDate);
    options.push({
      key: `yearly:${manualDate}`,
      label: String(reportingYear),
      preset: "manual",
      manualDate,
    });
  }

  return options;
}

export function buildCatchUpPeriodOptions(
  scheduleType: CatchUpScheduleType,
  today: Date = new Date(),
  count = 12,
): CatchUpPeriodOption[] {
  if (scheduleType === "weekly") {
    return buildWeeklyPeriodOptions(today, count);
  }
  if (scheduleType === "monthly") {
    return buildMonthlyPeriodOptions(today, count);
  }
  return buildYearlyPeriodOptions(today, count);
}

export function resolveDefaultPeriodKey(
  scheduleType: CatchUpScheduleType,
  today: Date = new Date(),
): string {
  return buildCatchUpPeriodOptions(scheduleType, today)[0]?.key ?? "";
}

export function findCatchUpPeriodOption(
  scheduleType: CatchUpScheduleType,
  periodKey: string,
  today: Date = new Date(),
): CatchUpPeriodOption | null {
  const options = buildCatchUpPeriodOptions(scheduleType, today);
  return options.find((opt) => opt.key === periodKey) ?? options[0] ?? null;
}

export function resolveCatchUpPeriodPayload(
  option: CatchUpPeriodOption,
): Pick<CatchUpPeriodOption, "preset" | "manualDate"> {
  return {
    preset: option.preset,
    manualDate: option.manualDate,
  };
}
