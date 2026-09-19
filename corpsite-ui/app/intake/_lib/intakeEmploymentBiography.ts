import type { IntakeDraftPayload } from "./intakeApi.client";
import { formatIntakePeriodForDisplay, formatIntakePeriodRange } from "./intakePeriodFormat";

export type IntakeEmploymentBiographyEntry = IntakeDraftPayload["employment_biography"][number] & {
  record_id?: string;
};

/** Adapts an unsaved legacy row for rendering; the next save persists only canonical keys. */
export function normalizeIntakeEmploymentBiographyEntry(raw: Record<string, unknown>, index: number): IntakeEmploymentBiographyEntry {
  const value = (key: string): string => String(raw[key] ?? "");
  const nullable = (key: string): string | null => value(key).trim() || null;
  return {
    record_id: value("record_id") || `legacy-${index}`,
    start_date: nullable("start_date") ?? nullable("year_from"),
    end_date: nullable("end_date") ?? nullable("year_to"),
    organization_original: value("organization_original") || value("organization"),
    organization_normalized: value("organization_normalized") || value("organization_original") || value("organization"),
    city: nullable("city"),
    position_original: value("position_original") || value("position"),
    position_normalized: value("position_normalized") || value("position_original") || value("position"),
    reason_for_leaving: nullable("reason_for_leaving"),
    note: nullable("note"),
    verification_status: raw.verification_status === "verified" || raw.verification_status === "rejected" || raw.verification_status === "requires_review" ? raw.verification_status : "unverified",
    evidence_document_ids: Array.isArray(raw.evidence_document_ids) ? raw.evidence_document_ids.map(String) : [],
  };
}

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
    start_date: "",
    end_date: null,
    organization_original: "",
    organization_normalized: "",
    city: null,
    position_original: "",
    position_normalized: "",
    reason_for_leaving: null,
    note: null,
    verification_status: "unverified",
    evidence_document_ids: [],
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
      const leftKey = employmentStartSortKey(left.item.start_date);
      const rightKey = employmentStartSortKey(right.item.start_date);
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
  return !String(item.end_date ?? "").trim();
}

export function employmentBiographyCellValue(value: string | null | undefined): string {
  const trimmed = String(value ?? "").trim();
  return trimmed || "—";
}

export function parseIntakeEmploymentFocusRowIndex(focusTestId: string | null | undefined): number | null {
  if (!focusTestId) return null;
  const match = focusTestId.match(/^intake-employment-year-(?:from|to)-(\d+)$/);
  return match ? Number(match[1]) : null;
}
