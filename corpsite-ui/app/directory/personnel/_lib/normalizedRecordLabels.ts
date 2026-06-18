// ADR-039 Phase 3E.1 — display labels for hr_import_normalized_records review UI.

export type NormalizedRecordKind = "training" | "certificate" | "category" | "education";

export const NORMALIZED_RECORD_KINDS: readonly NormalizedRecordKind[] = [
  "training",
  "certificate",
  "category",
  "education",
] as const;

/** Singular label for table rows, drawer, filters. */
export const NORMALIZED_RECORD_KIND_LABELS: Record<NormalizedRecordKind, string> = {
  training: "Обучение",
  certificate: "Сертификат",
  category: "Категория",
  education: "Образование",
};

/** Dashboard summary card titles (may differ in plural form). */
export const NORMALIZED_RECORD_KIND_SUMMARY_LABELS: Record<NormalizedRecordKind, string> = {
  training: "Обучение",
  certificate: "Сертификаты",
  category: "Категории",
  education: "Образование",
};

export function isNormalizedRecordKind(value: string): value is NormalizedRecordKind {
  return (NORMALIZED_RECORD_KINDS as readonly string[]).includes(value);
}

export function getNormalizedRecordKindLabel(
  kind: string | null | undefined,
  fallback = "—",
): string {
  if (!kind) return fallback;
  if (isNormalizedRecordKind(kind)) {
    return NORMALIZED_RECORD_KIND_LABELS[kind];
  }
  return kind;
}

export function getNormalizedRecordKindSummaryLabel(
  kind: NormalizedRecordKind,
): string {
  return NORMALIZED_RECORD_KIND_SUMMARY_LABELS[kind];
}
