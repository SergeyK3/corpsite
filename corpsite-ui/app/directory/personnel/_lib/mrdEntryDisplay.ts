/** Display helpers for MRD entry rows in the workspace table. */
export type MrdEntryRow = {
  entry_id: number;
  match_key: string;
  entity_scope: string;
  record_kind: string;
  effective_payload: Record<string, unknown>;
};

const DISPLAY_KEYS = ["full_name", "position_raw", "department", "iin", "personnel_number"] as const;

export function formatMrdEntryLabel(entry: MrdEntryRow): string {
  for (const key of DISPLAY_KEYS) {
    const value = entry.effective_payload[key];
    if (typeof value === "string" && value.trim()) return value.trim();
    if (typeof value === "number") return String(value);
  }
  return entry.match_key;
}

export function formatMrdEntrySecondary(entry: MrdEntryRow): string {
  const parts: string[] = [entry.record_kind];
  const position = entry.effective_payload.position_raw;
  const department = entry.effective_payload.department;
  if (typeof position === "string" && position.trim()) parts.push(position.trim());
  if (typeof department === "string" && department.trim()) parts.push(department.trim());
  return parts.join(" · ");
}

export function formatMrdRecordKindLabel(recordKind: string): string {
  switch (recordKind) {
    case "roster":
      return "Состав";
    case "education":
      return "Образование";
    case "training":
      return "Обучение";
    case "certificate":
      return "Сертификат";
    default:
      return recordKind;
  }
}
