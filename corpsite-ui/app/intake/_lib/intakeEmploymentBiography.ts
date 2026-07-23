import type { IntakeDraftPayload } from "./intakeApi.client";
import { formatIntakePeriodForDisplay, formatIntakePeriodRange } from "./intakePeriodFormat";

export type IntakeEmploymentBiographyEntry = IntakeDraftPayload["employment_biography"][number] & {
  record_id?: string;
};

function createEmploymentRecordId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `employment-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function ensureEmploymentBiographyRecordId(
  entry: Pick<IntakeEmploymentBiographyEntry, "record_id">,
  index: number,
): string {
  const existing = String(entry.record_id ?? "").trim();
  if (existing) return existing;
  return `legacy-${index}`;
}

export type IntakeEmploymentBiographyRow = {
  item: IntakeEmploymentBiographyEntry;
  index: number;
};

export const INTAKE_EMPLOYMENT_BIOGRAPHY_SHOW_TENURE_COLUMN = true;

export const INTAKE_EMPLOYMENT_TENURE_OVERLAP_HINT =
  "Пересекается с другим периодом — в общем стаже учитывается один раз";

export function emptyIntakeEmploymentBiographyEntry(): IntakeEmploymentBiographyEntry {
  return {
    record_id: createEmploymentRecordId(),
    organization: "",
    position: "",
    year_from: "",
    year_to: "",
    reason_for_leaving: "",
  };
}

function employmentStartSortKey(raw: string | null | undefined): string {
  return String(raw ?? "").trim();
}

export function sortIntakeEmploymentBiographyRows(
  items: readonly IntakeEmploymentBiographyEntry[],
): IntakeEmploymentBiographyRow[] {
  return items
    .map((item, index) => ({ item, index }))
    .sort((left, right) => {
      const leftKey = employmentStartSortKey(left.item.year_from);
      const rightKey = employmentStartSortKey(right.item.year_from);
      if (leftKey === rightKey) return left.index - right.index;
      if (!leftKey) return 1;
      if (!rightKey) return -1;
      return rightKey.localeCompare(leftKey);
    });
}

export function formatIntakeEmploymentPeriodCell(
  yearFrom: string | null | undefined,
  yearTo: string | null | undefined,
): string {
  const from = formatIntakePeriodForDisplay(yearFrom);
  const toRaw = String(yearTo ?? "").trim();
  if (!from && !toRaw) return "—";
  if (!toRaw) {
    return from ? `${from} — наст. время` : "наст. время";
  }
  return formatIntakePeriodRange(yearFrom, yearTo);
}

export function isIntakeEmploymentCurrent(item: IntakeEmploymentBiographyEntry): boolean {
  return !String(item.year_to ?? "").trim();
}

export function employmentBiographyCellValue(value: string | null | undefined): string {
  const trimmed = String(value ?? "").trim();
  return trimmed || "—";
}
