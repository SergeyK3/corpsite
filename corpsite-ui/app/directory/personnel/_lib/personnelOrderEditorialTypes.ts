/**
 * Spike types for WP-PO-EDIT-001 — editorial document model.
 * Non-production: not wired to persistence, API, editor UI, or print/PDF pipeline.
 * Ratified: Architecture Approved for Implementation (see PO-EDIT-001 §0).
 */

export type PersonnelOrderEditorialLocale = "kk" | "ru";

export type PersonnelOrderEditorialBlockKind =
  | "title"
  | "preamble"
  | "closing"
  | "item_body"
  | "item_basis";

export type PersonnelOrderBasisType =
  | "PERSONAL_APPLICATION"
  | "MEMO"
  | "MANAGEMENT_SUBMISSION"
  | "MEDICAL_CONCLUSION"
  | "COMMISSION_PROTOCOL"
  | "COURT_ACT"
  | "OTHER";

/** Plain-text editorial cell: generated snapshot + optional manual override. */
export type PersonnelOrderEditorialTextCell = {
  generated: string | null;
  override: string | null;
  /** Hash of structured inputs used when `generated` was last written. */
  sourceFingerprint: string | null;
  generatedAt: string | null;
  editedAt: string | null;
  editedBy: number | null;
};

export function effectiveEditorialText(cell: PersonnelOrderEditorialTextCell | null | undefined): string {
  if (!cell) return "";
  const override = String(cell.override ?? "").trim();
  if (override) return override;
  return String(cell.generated ?? "").trim();
}

export function isEditorialManuallyEdited(cell: PersonnelOrderEditorialTextCell | null | undefined): boolean {
  return Boolean(cell && String(cell.override ?? "").trim());
}

export function isEditorialStale(
  cell: PersonnelOrderEditorialTextCell | null | undefined,
  currentFingerprint: string | null | undefined,
): boolean {
  if (!cell || !isEditorialManuallyEdited(cell)) return false;
  const stored = String(cell.sourceFingerprint ?? "").trim();
  const current = String(currentFingerprint ?? "").trim();
  if (!stored || !current) return false;
  return stored !== current;
}

export type PersonnelOrderEditorialState = {
  orderId: number;
  locale: PersonnelOrderEditorialLocale;
  title: PersonnelOrderEditorialTextCell;
  preamble: PersonnelOrderEditorialTextCell;
  closing: PersonnelOrderEditorialTextCell;
  /** Code/contract version stamped at generate time (EDIT-002). */
  generatorVersion: string | null;
  /** Reserved for EDIT-004 DB clause library. */
  templateSetVersion: number | null;
  revision: number;
};

export type PersonnelOrderItemEditorialState = {
  orderItemId: number;
  locale: PersonnelOrderEditorialLocale;
  body: PersonnelOrderEditorialTextCell;
  basis: PersonnelOrderEditorialTextCell;
  generatorVersion: string | null;
  templateSetVersion: number | null;
  revision: number;
};

export type PersonnelOrderItemBasisFact = {
  basisType: PersonnelOrderBasisType;
  subjectEmployeeId: number | null;
  subjectEmployeeName: string | null;
  /** Optional pre-stored morphological forms — never invent if missing. */
  subjectEmployeeNameGenitiveRu?: string | null;
  subjectEmployeeNamePossessiveKk?: string | null;
  documentDate?: string | null;
  documentNumber?: string | null;
  freeText?: string | null;
};
