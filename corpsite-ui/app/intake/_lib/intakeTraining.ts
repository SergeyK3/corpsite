import {
  INTAKE_TRAINING_DOCUMENT_TYPE_OPTIONS,
  type IntakeTraining,
  type IntakeTrainingDocumentType,
} from "./intakeApi.client";
import {
  isIncompleteIntakePeriodDate,
  isValidIntakeFullDateIso,
} from "./intakeDateValidation";
import { formatIntakePeriodForDisplay, formatIntakePeriodRange } from "./intakePeriodFormat";

export type IntakeTrainingEntry = IntakeTraining;

export type IntakeTrainingRow = {
  item: IntakeTrainingEntry;
  index: number;
};

const TRAINING_DOCUMENT_TYPES = new Set<IntakeTrainingDocumentType>(
  INTAKE_TRAINING_DOCUMENT_TYPE_OPTIONS.map((option) => option.value),
);

export function normalizeIntakeTrainingDocumentType(
  raw: string | null | undefined,
): IntakeTrainingDocumentType {
  const value = String(raw ?? "").trim().toLowerCase();
  if (TRAINING_DOCUMENT_TYPES.has(value as IntakeTrainingDocumentType)) {
    return value as IntakeTrainingDocumentType;
  }
  return "certificate";
}

export function resolveIntakeTrainingYearTo(item: Pick<IntakeTrainingEntry, "year_to" | "year">): string {
  const yearTo = String(item.year_to ?? "").trim();
  if (yearTo) return yearTo;
  return String(item.year ?? "").trim();
}

export function normalizeIntakeTrainingEntry(
  item: Partial<IntakeTrainingEntry> & Record<string, unknown>,
): IntakeTrainingEntry {
  const yearTo = String(item.year_to ?? item.year ?? "");
  return {
    institution: String(item.institution ?? ""),
    course_name: String(item.course_name ?? ""),
    year_from: String(item.year_from ?? ""),
    year_to: yearTo,
    document_type: normalizeIntakeTrainingDocumentType(String(item.document_type ?? "")),
    document_number: String(item.document_number ?? ""),
    hours: String(item.hours ?? ""),
    hours_is_manual: Boolean(item.hours_is_manual),
  };
}

export function emptyIntakeTrainingEntry(): IntakeTrainingEntry {
  return normalizeIntakeTrainingEntry({});
}

export function intakeTrainingCellValue(value: string | null | undefined): string {
  const trimmed = String(value ?? "").trim();
  return trimmed || "—";
}

export function getIntakeTrainingDocumentTypeLabel(
  value: IntakeTrainingDocumentType | string | null | undefined,
): string {
  const normalized = normalizeIntakeTrainingDocumentType(value);
  return (
    INTAKE_TRAINING_DOCUMENT_TYPE_OPTIONS.find((option) => option.value === normalized)?.label ??
    normalized
  );
}

export function formatIntakeTrainingPeriodCell(item: Pick<IntakeTrainingEntry, "year_from" | "year_to" | "year">): string {
  const from = formatIntakePeriodForDisplay(item.year_from);
  const to = formatIntakePeriodForDisplay(resolveIntakeTrainingYearTo(item));
  if (!from && !to) return "—";
  return formatIntakePeriodRange(item.year_from, resolveIntakeTrainingYearTo(item));
}

export function formatIntakeTrainingHoursCell(hours: string | null | undefined): string {
  const trimmed = String(hours ?? "").trim();
  if (!trimmed) return "—";
  return trimmed;
}

export function countInclusiveCalendarDays(fromIso: string, toIso: string): number | null {
  if (!isValidIntakeFullDateIso(fromIso) || !isValidIntakeFullDateIso(toIso)) {
    return null;
  }
  const fromParts = fromIso.slice(0, 10).split("-").map(Number);
  const toParts = toIso.slice(0, 10).split("-").map(Number);
  const fromDate = Date.UTC(fromParts[0], fromParts[1] - 1, fromParts[2]);
  const toDate = Date.UTC(toParts[0], toParts[1] - 1, toParts[2]);
  if (fromDate > toDate) return null;
  return Math.floor((toDate - fromDate) / 86_400_000) + 1;
}

export type TrainingHoursResolution = {
  hours: string;
  note: string;
  isManual: boolean;
  periodError: string | null;
};

export function resolveTrainingHoursState(item: IntakeTrainingEntry): TrainingHoursResolution {
  if (item.hours_is_manual && String(item.hours ?? "").trim()) {
    return {
      hours: String(item.hours).trim(),
      note: "По документу",
      isManual: true,
      periodError: null,
    };
  }

  const yearFrom = String(item.year_from ?? "").trim();
  const yearTo = resolveIntakeTrainingYearTo(item);

  if (!yearFrom && !yearTo) {
    return { hours: "", note: "", isManual: false, periodError: null };
  }

  if (isIncompleteIntakePeriodDate(yearFrom) || isIncompleteIntakePeriodDate(yearTo)) {
    return {
      hours: "",
      note: "",
      isManual: false,
      periodError: "Укажите полные даты начала и окончания в формате ДД.ММ.ГГГГ",
    };
  }

  if (!yearFrom || !yearTo) {
    return {
      hours: "",
      note: "",
      isManual: false,
      periodError: "Укажите дату начала и дату окончания",
    };
  }

  const days = countInclusiveCalendarDays(yearFrom, yearTo);
  if (days === null) {
    return {
      hours: "",
      note: "",
      isManual: false,
      periodError: "Дата начала не может быть позже даты окончания",
    };
  }

  return {
    hours: String(days * 8),
    note: `Расчётно: ${days} дней × 8 часов`,
    isManual: false,
    periodError: null,
  };
}

export function reconcileTrainingEntryHours(item: IntakeTrainingEntry): IntakeTrainingEntry {
  if (item.hours_is_manual) return item;
  const resolved = resolveTrainingHoursState(item);
  return {
    ...item,
    hours: resolved.periodError ? "" : resolved.hours,
  };
}

export function applyTrainingEntryPatch(
  item: IntakeTrainingEntry,
  patch: Partial<IntakeTrainingEntry>,
): IntakeTrainingEntry {
  let next = normalizeIntakeTrainingEntry({ ...item, ...patch });

  if ("hours" in patch) {
    const trimmed = String(patch.hours ?? "").trim();
    next.hours = trimmed;
    next.hours_is_manual = trimmed !== "";
  }

  const datesChanged =
    "year_from" in patch || "year_to" in patch || "year" in patch;

  if (!next.hours_is_manual && (datesChanged || ("hours" in patch && !next.hours))) {
    next = reconcileTrainingEntryHours(next);
  }

  return next;
}

export function isInvalidIntakeTrainingPeriodRange(item: Pick<IntakeTrainingEntry, "year_from" | "year_to" | "year">): boolean {
  const yearFrom = String(item.year_from ?? "").trim();
  const yearTo = resolveIntakeTrainingYearTo(item);
  if (!yearFrom || !yearTo) return false;
  if (isIncompleteIntakePeriodDate(yearFrom) || isIncompleteIntakePeriodDate(yearTo)) return false;
  return countInclusiveCalendarDays(yearFrom, yearTo) === null;
}

function trainingStartSortKey(item: Pick<IntakeTrainingEntry, "year_from" | "year_to" | "year">): string {
  return String(item.year_from ?? resolveIntakeTrainingYearTo(item) ?? "").trim();
}

export function sortIntakeTrainingRows(items: readonly IntakeTrainingEntry[]): IntakeTrainingRow[] {
  return items
    .map((item, index) => ({ item, index }))
    .sort((left, right) => {
      const leftKey = trainingStartSortKey(left.item);
      const rightKey = trainingStartSortKey(right.item);
      if (leftKey === rightKey) return left.index - right.index;
      if (!leftKey) return 1;
      if (!rightKey) return -1;
      return rightKey.localeCompare(leftKey);
    });
}

export function parseIntakeTrainingFocusRowIndex(focusTestId: string | null | undefined): number | null {
  if (!focusTestId) return null;
  const match = focusTestId.match(/^intake-training-year-(?:from|to)-(\d+)$/);
  return match ? Number(match[1]) : null;
}
