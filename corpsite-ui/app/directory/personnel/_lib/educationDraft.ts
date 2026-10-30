import { emptyServiceLengthDraft, refreshServiceLengthContext } from "./serviceLengthDraft";
import type { ServiceLengthDraft } from "./serviceLengthDraft";
import type { PersonnelDocumentContext } from "./personnelOrderDocumentContext";

export type EducationDraft = Omit<ServiceLengthDraft, "contract" | "service_length" | "basis"> & {
  contract: "education-information-change-v1";
  source_position_name: string;
  source_position_name_kk: string;
  source_position_id?: number | null;
  education: { level_code?: string | null; medical_specialty_id?: number | null; level_ru: string; level_kk: string; specialty_ru: string; specialty_kk: string };
  education_document: { kind_code?: string | null; kind_ru: string; kind_kk: string; number: string; issued_at: string; issued_at_status?: "KNOWN" | "TO_CLARIFY" };
};

export function emptyEducationDraft(): EducationDraft {
  const { contract: _, service_length: __, basis: ___, ...subject } = emptyServiceLengthDraft();
  return { ...subject, contract: "education-information-change-v1", source_position_name: "", source_position_name_kk: "",
    education: { level_ru: "", level_kk: "", specialty_ru: "", specialty_kk: "" },
    education_document: { kind_ru: "", kind_kk: "", number: "", issued_at: "", issued_at_status: "KNOWN" } };
}

export function educationDraftFromRecord(source: Partial<EducationDraft>, effectiveDate = ""): EducationDraft {
  const blank = emptyEducationDraft();
  return { ...blank, ...source, contract: blank.contract, effective_date: source.effective_date || effectiveDate,
    subject_mode: source.unresolved_subject ? "MANUAL" : source.subject_mode || "DIRECTORY",
    document_forms_ru: { ...blank.document_forms_ru, ...source.document_forms_ru },
    document_forms_kk: { ...blank.document_forms_kk, ...source.document_forms_kk },
    document_org_unit: { ...blank.document_org_unit, ...source.document_org_unit },
    education: { ...blank.education, ...source.education }, education_document: { ...blank.education_document, ...source.education_document } };
}

export function refreshEducationContext(draft: EducationDraft, context: PersonnelDocumentContext, previous?: PersonnelDocumentContext | null): EducationDraft {
  if (draft.subject_mode === "MANUAL") return draft;
  const refreshed = refreshServiceLengthContext({ ...emptyServiceLengthDraft(), ...draft, contract: "service-length-change-v1" }, context, previous);
  const changed = Boolean(previous && previous.owners.employee !== "" && previous.owners.position !== context.owners.position);
  const unitChanged = Boolean(previous && previous.owners.employee !== "" && previous.owners.unit !== context.owners.unit);
  const savedPosition = draft.source_position_id != null && !changed;
  const savedUnit = draft.document_org_unit.unit_id != null && !unitChanged;
  return { ...draft, employee_id: refreshed.employee_id, source_employee_name: refreshed.source_employee_name,
    source_position_id: changed ? null : draft.source_position_id,
    document_forms_ru: { ...refreshed.document_forms_ru, ...(savedPosition ? { position_document_genitive_ru: draft.document_forms_ru.position_document_genitive_ru } : {}) },
    document_forms_kk: { ...refreshed.document_forms_kk, ...(savedPosition ? { position_document_possessive_kk: draft.document_forms_kk.position_document_possessive_kk } : {}) },
    document_org_unit: savedUnit ? draft.document_org_unit : refreshed.document_org_unit,
    source_position_name_kk: savedPosition ? draft.source_position_name_kk : changed || !draft.source_position_name_kk ? context.values.position_title_kk || "" : draft.source_position_name_kk,
    source_position_name: savedPosition ? draft.source_position_name : changed || !draft.source_position_name ? context.values.position_document_nominative_ru || "" : draft.source_position_name };
}

export function switchEducationSubject(draft: EducationDraft, mode: "DIRECTORY" | "MANUAL"): EducationDraft {
  const blank = emptyEducationDraft();
  return { ...draft, subject_mode: mode, employee_id: null, source_employee_name: "", unresolved_subject: undefined,
    source_position_id: null, source_position_name: "", source_position_name_kk: "", document_forms_ru: blank.document_forms_ru,
    document_forms_kk: blank.document_forms_kk, document_org_unit: blank.document_org_unit };
}

export function educationOrderPayload(draft: EducationDraft): EducationDraft {
  return { ...draft, education_document: { ...draft.education_document,
    issued_at_status: draft.education_document.issued_at_status || "KNOWN",
    issued_at: draft.education_document.issued_at_status === "TO_CLARIFY" ? "" : draft.education_document.issued_at },
    employee_id: draft.subject_mode === "MANUAL" ? null : draft.employee_id,
    unresolved_subject: draft.subject_mode === "MANUAL" ? { full_name: draft.source_employee_name } : undefined };
}

function validDay(value: string): boolean {
  const parsed = new Date(value + "T00:00:00Z");
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value && parsed.getUTCFullYear() >= 1900;
}

export function educationErrors(draft: EducationDraft): string[] {
  const errors: string[] = [];
  if (draft.subject_mode === "MANUAL") {
    if (!draft.source_employee_name.trim()) errors.push("Укажите ФИО сотрудника вручную.");
  } else if (!Number.isSafeInteger(draft.employee_id) || Number(draft.employee_id) < 1) errors.push("Выберите сотрудника.");
  for (const [value, label] of [
    [draft.document_forms_ru.employee_full_name_genitive_ru, "ФИО в родительном падеже RU"],
    [draft.document_forms_kk.employee_full_name_genitive_kk, "ФИО в ілік септік KK"],
    [draft.document_forms_ru.position_document_genitive_ru, "Должность в родительном падеже RU"],
    [draft.document_forms_kk.position_document_possessive_kk, "Должность в тексте KK"],
    [draft.document_org_unit.document_genitive_ru, "Подразделение в родительном падеже RU"],
    [draft.document_org_unit.document_genitive_kk, "Подразделение в ілік септік KK"],
    [draft.education_document.kind_ru, "Вид документа RU"], [draft.education_document.kind_kk, "Вид документа KK"],
    [draft.education_document.number, "Номер документа"],
  ]) if (!value.trim()) errors.push(`Заполните: ${label}.`);
  if (!validDay(draft.effective_date)) errors.push("Укажите полную дату начала действия.");
  const issuedStatus = draft.education_document.issued_at_status || "KNOWN";
  if (issuedStatus !== "KNOWN" && issuedStatus !== "TO_CLARIFY") errors.push("Выберите состояние даты выдачи документа.");
  else if (issuedStatus === "KNOWN" && !validDay(draft.education_document.issued_at)) errors.push("Укажите полную дату выдачи документа или выберите «Уточнить».");
  return errors;
}

// Match ID60's literal markers without rewriting its stored RU/KK wording.
export const EDUCATION_MARKERS = {
  ru: { "[дата начала действия]": "effective_date.ru", "[должность]": "position.document_genitive_ru", "[подразделение]": "org_unit.document_genitive_ru",
    "[Ф.И.О. сотрудника в родительном падеже]": "employee.full_name_genitive_ru", "[уровень образования]": "education.level_ru", "[специальность]": "education.specialty_ru",
    "[вид документа]": "education_document.kind_ru", "[номер]": "education_document.number", "[дата выдачи]": "education_document.issued_ru" },
  kk: { "[күні]": "effective_date.kk", "[лауазымы]": "position.document_possessive_kk", "[бөлімшесі]": "org_unit.document_genitive_kk",
    "[қызметкердің аты-жөні, ілік септігінде]": "employee.full_name_genitive_kk", "[білім деңгейі]": "education.level_kk", "[мамандық]": "education.specialty_kk",
    "[құжат түрі]": "education_document.kind_kk", "[нөмір]": "education_document.number", "[берілген күні]": "education_document.issued_kk" },
};

export function educationLiteralTokens(field: string, value: string): string[] {
  if (!field.startsWith("body_template_") && !field.startsWith("basis_template_") && !field.startsWith("preamble_")) return [];
  const locale = field.endsWith("_kk") ? "kk" : "ru";
  return Object.entries(EDUCATION_MARKERS[locale]).filter(([marker]) => value.includes(marker)).map(([, token]) => token);
}
