/** Допустимое окно создания эталонов (frontend-only). */
import type { MonthlyReferenceSummary } from "./mrdApi.client";
import { groupMrdSourcesByPeriod } from "./mrdDisplay";

export function reportPeriodIso(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, "0")}-01`;
}

export function monthInputFromIso(iso: string): string {
  return iso.slice(0, 7);
}

export function shiftReportPeriod(iso: string, deltaMonths: number): string {
  const [year, month] = iso.slice(0, 10).split("-").map(Number);
  const date = new Date(year, month - 1 + deltaMonths, 1);
  return reportPeriodIso(date.getFullYear(), date.getMonth() + 1);
}

export function nextReportPeriod(iso: string): string {
  return shiftReportPeriod(iso, 1);
}

/** Предыдущий, текущий и следующий календарные месяцы относительно referenceDate. */
export function getCreationWindowPeriods(referenceDate: Date = new Date()): string[] {
  const anchor = reportPeriodIso(referenceDate.getFullYear(), referenceDate.getMonth() + 1);
  return [shiftReportPeriod(anchor, -1), anchor, shiftReportPeriod(anchor, 1)];
}

export function isInCreationWindow(periodIso: string, referenceDate: Date = new Date()): boolean {
  const key = periodIso.slice(0, 10);
  return getCreationWindowPeriods(referenceDate).includes(key);
}

export function collectExistingReportPeriods(items: MonthlyReferenceSummary[]): Set<string> {
  return new Set(items.map((item) => item.report_period.slice(0, 10)));
}

/** Одна строка журнала на период — действующая (рабочая) версия. */
export function collapseMrdJournalRows(
  items: MonthlyReferenceSummary[],
  activeByPeriod: Record<string, number>,
): MonthlyReferenceSummary[] {
  return groupMrdSourcesByPeriod(items)
    .map((group) => {
      const activeId = activeByPeriod[group.reportPeriod];
      return (
        group.items.find((item) => item.mrd_id === activeId) ??
        group.items.find((item) => item.status === "ACTIVE") ??
        group.items[0] ??
        null
      );
    })
    .filter((row): row is MonthlyReferenceSummary => row != null)
    .sort((a, b) => b.report_period.localeCompare(a.report_period));
}

export type CreateNextPeriodOffer = {
  allowed: boolean;
  targetPeriod: string | null;
  reason?: "exists" | "out_of_window" | "no_next";
};

export function evaluateCreateNextPeriodOffer(
  sourcePeriodIso: string,
  existingPeriods: Set<string>,
  referenceDate: Date = new Date(),
): CreateNextPeriodOffer {
  const targetPeriod = nextReportPeriod(sourcePeriodIso);
  if (existingPeriods.has(targetPeriod)) {
    return { allowed: false, targetPeriod: null, reason: "exists" };
  }
  if (!isInCreationWindow(targetPeriod, referenceDate)) {
    return { allowed: false, targetPeriod: null, reason: "out_of_window" };
  }
  return { allowed: true, targetPeriod };
}

export function listAllowedTargetPeriodOptions(
  sourcePeriodIso: string,
  existingPeriods: Set<string>,
  referenceDate: Date = new Date(),
): Array<{ iso: string; monthInput: string }> {
  const offer = evaluateCreateNextPeriodOffer(sourcePeriodIso, existingPeriods, referenceDate);
  if (!offer.allowed || !offer.targetPeriod) return [];
  return [{ iso: offer.targetPeriod, monthInput: monthInputFromIso(offer.targetPeriod) }];
}

export function validateCreateTargetPeriod(
  targetMonthInput: string,
  sourcePeriodIso: string,
  existingPeriods: Set<string>,
  referenceDate: Date = new Date(),
): string | null {
  const normalized = targetMonthInput.trim();
  if (!/^\d{4}-\d{2}$/.test(normalized)) {
    return "Укажите период в формате ГГГГ-ММ.";
  }
  const targetIso = `${normalized}-01`;
  if (existingPeriods.has(targetIso)) {
    return "Для выбранного периода уже существует эталон.";
  }
  const expectedNext = nextReportPeriod(sourcePeriodIso);
  if (targetIso !== expectedNext) {
    return "Можно создать эталон только для следующего месяца после исходного периода.";
  }
  if (!isInCreationWindow(targetIso, referenceDate)) {
    return "Период вне допустимого окна: доступны только предыдущий, текущий и следующий месяц.";
  }
  return null;
}

export function resolveSuggestedCreation(
  journalRows: MonthlyReferenceSummary[],
  existingPeriods: Set<string>,
  referenceDate: Date = new Date(),
): { source: MonthlyReferenceSummary | null; targetPeriod: string | null } {
  for (const row of journalRows) {
    const offer = evaluateCreateNextPeriodOffer(row.report_period, existingPeriods, referenceDate);
    if (offer.allowed && offer.targetPeriod) {
      return { source: row, targetPeriod: offer.targetPeriod };
    }
  }
  return { source: null, targetPeriod: null };
}

export type WorkingJournalRow = {
  reportPeriod: string;
  baseline: MonthlyReferenceSummary | null;
};

/** Строки рабочего журнала: только предыдущий, текущий и следующий месяц. */
export function buildWorkingJournalRows(
  items: MonthlyReferenceSummary[],
  activeByPeriod: Record<string, number>,
  referenceDate: Date = new Date(),
): WorkingJournalRow[] {
  const windowPeriods = getCreationWindowPeriods(referenceDate);
  const windowSet = new Set(windowPeriods);
  const inWindowItems = items.filter((item) => windowSet.has(item.report_period.slice(0, 10)));
  const collapsed = collapseMrdJournalRows(inWindowItems, activeByPeriod);
  const byPeriod = new Map(collapsed.map((row) => [row.report_period.slice(0, 10), row]));
  return windowPeriods.map((reportPeriod) => ({
    reportPeriod,
    baseline: byPeriod.get(reportPeriod) ?? null,
  }));
}

export type CreateBaselineOffer = {
  allowed: boolean;
  sourceMrdId: number | null;
  targetPeriod: string;
};

/** Создание эталона для периода на основе действующего эталона предыдущего месяца. */
export function evaluateCreateBaselineOffer(
  targetPeriodIso: string,
  existingPeriods: Set<string>,
  baselineByPeriod: Map<string, MonthlyReferenceSummary>,
  referenceDate: Date = new Date(),
): CreateBaselineOffer {
  const targetPeriod = targetPeriodIso.slice(0, 10);
  if (existingPeriods.has(targetPeriod)) {
    return { allowed: false, sourceMrdId: null, targetPeriod };
  }
  if (!isInCreationWindow(targetPeriod, referenceDate)) {
    return { allowed: false, sourceMrdId: null, targetPeriod };
  }
  const sourcePeriod = shiftReportPeriod(targetPeriod, -1);
  const source = baselineByPeriod.get(sourcePeriod) ?? null;
  if (!source || source.status !== "ACTIVE") {
    return { allowed: false, sourceMrdId: null, targetPeriod };
  }
  return { allowed: true, sourceMrdId: source.mrd_id, targetPeriod };
}
