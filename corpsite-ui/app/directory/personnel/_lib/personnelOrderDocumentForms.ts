import { calculateKazakhPositionPossessive, calculateKazakhOrgUnitGenitive, firstNonEmpty } from "./kazakhDocumentForms";

type PositionReference = {
  id?: number | null;
  name?: string | null;
  name_kk?: string | null;
  code?: string | null;
  document_possessive_kk?: string | null;
  document_nominative_ru?: string | null;
} | null | undefined;

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? value as Record<string, unknown> : {};
}

function firstText(...values: unknown[]): string {
  return values.find((value): value is string => typeof value === "string" && Boolean(value.trim()))?.trim() || "";
}

/** Shared by both leave types and both editors. No RU→KK translation dictionary. */
export function resolvePersonnelOrderDocumentForms(position: PositionReference, employee?: unknown) {
  const source = record(employee);
  const russian = firstText(position?.name);
  return {
    position_document_possessive_kk: firstText(
      record(source.document_forms_kk).position_document_possessive_kk,
      source.position_document_possessive_kk, position?.document_possessive_kk,
      calculateKazakhPositionPossessive(position?.name_kk).value,
    ),
    position_document_nominative_ru: firstText(
      record(source.document_forms_ru).position_document_nominative_ru,
      source.position_document_nominative_ru, position?.document_nominative_ru,
      russian ? russian[0].toLocaleLowerCase("ru-RU") + russian.slice(1) : "",
    ),
  };
}

export function resolvePersonnelOrderOrgUnitForms(unit: { name?: unknown; name_kk?: unknown; document_genitive_kk?: unknown } | null | undefined) {
  return {
    org_unit_title_ru: firstNonEmpty(unit?.name),
    org_unit_document_genitive_kk: firstNonEmpty(unit?.document_genitive_kk, calculateKazakhOrgUnitGenitive(unit?.name_kk).value),
  };
}
