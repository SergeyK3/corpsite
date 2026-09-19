import type { IntakeDraftPayload } from "./intakeApi.client";
import { formatIntakePeriodForDisplay } from "./intakePeriodFormat";
import { normalizeIntakeRecordId } from "./intakeRecordId";

export type IntakeRelativeEntry = IntakeDraftPayload["relatives"][number];

export type IntakeRelativeRow = {
  item: IntakeRelativeEntry;
  index: number;
};

export function emptyIntakeRelativeEntry(): IntakeRelativeEntry {
  return {
    record_id: normalizeIntakeRecordId(undefined),
    relationship: "",
    relationship_other: "",
    full_name: "",
    birth_date: "",
    workplace: "",
    birth_year: "",
    work_place: "",
  };
}

export function intakeRelativeCellValue(value: string | null | undefined): string {
  const trimmed = String(value ?? "").trim();
  return trimmed || "—";
}

export function formatIntakeRelativeBirthCell(birthYear: string | null | undefined): string {
  return formatIntakePeriodForDisplay(birthYear) || "—";
}

export function sortIntakeRelativeRows(items: readonly IntakeRelativeEntry[]): IntakeRelativeRow[] {
  return items.map((item, index) => ({ item, index }));
}

export function parseIntakeRelativeFocusRowIndex(focusTestId: string | null | undefined): number | null {
  if (!focusTestId) return null;
  const match = focusTestId.match(/^intake-relative-birth-year-(\d+)$/);
  return match ? Number(match[1]) : null;
}
