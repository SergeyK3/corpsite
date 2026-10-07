import { calculateKazakhPositionPossessive, calculateKazakhOrgUnitGenitive, firstNonEmpty } from "./kazakhDocumentForms";

type PositionReference = {
  job_code?: string | null;
  job_nameru?: string | null;
  job_namekk?: string | null;
  job_namekk_doc?: string | null;
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

/** Explicit employee case forms shared by the personnel order constructors. */
export function savedKazakhEmployeeNameForm(employee: unknown, form: "dative" | "genitive"): string {
  const source=record(employee);
  const key=`employee_full_name_${form}_kk`;
  return firstText(record(source.document_forms_kk)[key],record(source.name)[`full_name_${form}_kk`],source[key]);
}

/** Shared by every order type and both editors. Saved forms precede catalog defaults. */
export function resolvePersonnelOrderDocumentForms(position: PositionReference, employee?: unknown) {
  const source = record(employee);
  if (source.has_current_assignment === false) position = null;
  const russian = firstText(position?.name);
  return {
    position_document_possessive_kk: firstText(
      record(source.document_forms_kk).position_document_possessive_kk,
      source.position_document_possessive_kk, position?.document_possessive_kk,
      position?.job_namekk_doc,
      calculateKazakhPositionPossessive(position?.name_kk).value,
    ),
    position_document_nominative_ru: firstText(
      record(source.document_forms_ru).position_document_nominative_ru,
      source.position_document_nominative_ru, position?.document_nominative_ru,
      position?.job_nameru,
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
