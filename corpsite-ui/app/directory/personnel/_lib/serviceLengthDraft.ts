import type { QualificationCategoryDraft } from "./qualificationCategoryDraft";
import { emptyCategoryOrderDraft } from "./qualificationCategoryDraft";
import { refreshCategoryDocumentContext, type PersonnelDocumentContext } from "./personnelOrderDocumentContext";
import type { ManualOrderSubject } from "./personnelOrderManualSubject";

export type ServiceLengthDraft = Pick<QualificationCategoryDraft, "employee_id" | "source_employee_name" | "document_forms_ru" | "document_forms_kk" | "document_org_unit"> & {
  contract: "service-length-change-v1";
  subject_mode?: "DIRECTORY" | "MANUAL";
  unresolved_subject?: ManualOrderSubject;
  effective_date: string;
  service_length: { new_ru: string; new_kk: string };
  basis: { ru: string; kk: string };
};

export function emptyServiceLengthDraft(): ServiceLengthDraft {
  const { employee_id, source_employee_name, document_forms_ru, document_forms_kk, document_org_unit } = emptyCategoryOrderDraft();
  return { contract: "service-length-change-v1", subject_mode: "DIRECTORY", employee_id, source_employee_name, document_forms_ru, document_forms_kk,
    document_org_unit, effective_date: "", service_length: { new_ru: "", new_kk: "" }, basis: { ru: "", kk: "" } };
}

export function serviceLengthDraftFromRecord(source: Partial<ServiceLengthDraft>, effectiveDate = ""): ServiceLengthDraft {
  const blank = emptyServiceLengthDraft();
  return { ...blank, ...source, contract: blank.contract, effective_date: source.effective_date || effectiveDate,
    subject_mode: source.unresolved_subject ? "MANUAL" : source.subject_mode || "DIRECTORY",
    document_forms_ru: { ...blank.document_forms_ru, ...source.document_forms_ru },
    document_forms_kk: { ...blank.document_forms_kk, ...source.document_forms_kk },
    document_org_unit: { ...blank.document_org_unit, ...source.document_org_unit },
    service_length: { ...blank.service_length, ...source.service_length }, basis: { ...blank.basis, ...source.basis } };
}

export function refreshServiceLengthContext(draft: ServiceLengthDraft, context: PersonnelDocumentContext, previous?: PersonnelDocumentContext | null): ServiceLengthDraft {
  if (draft.subject_mode === "MANUAL") return draft;
  const refreshed = refreshCategoryDocumentContext({ ...emptyCategoryOrderDraft(), ...draft, contract: undefined }, context, previous);
  return { ...draft, employee_id: refreshed.employee_id, source_employee_name: refreshed.source_employee_name,
    document_forms_ru: refreshed.document_forms_ru, document_forms_kk: refreshed.document_forms_kk, document_org_unit: refreshed.document_org_unit };
}

export function switchServiceLengthSubject(draft: ServiceLengthDraft, mode: "DIRECTORY" | "MANUAL"): ServiceLengthDraft {
  const blank = emptyServiceLengthDraft();
  return { ...draft, subject_mode: mode, employee_id: null, source_employee_name: "", unresolved_subject: undefined,
    document_forms_ru: blank.document_forms_ru, document_forms_kk: blank.document_forms_kk, document_org_unit: blank.document_org_unit };
}

export function serviceLengthOrderPayload(draft: ServiceLengthDraft): ServiceLengthDraft {
  const manual = draft.subject_mode === "MANUAL";
  return { ...draft, employee_id: manual ? null : draft.employee_id,
    unresolved_subject: manual ? { full_name: draft.source_employee_name } : undefined };
}

export function serviceLengthErrors(draft: ServiceLengthDraft): string[] {
  const errors: string[] = [];
  if (draft.subject_mode === "MANUAL") {
    if (!draft.source_employee_name.trim()) errors.push("Укажите ФИО сотрудника вручную.");
  } else if (!Number.isSafeInteger(draft.employee_id) || Number(draft.employee_id) < 1) errors.push("Выберите сотрудника.");
  for (const [value, label] of [
    [draft.document_forms_ru.employee_full_name_genitive_ru, "ФИО в родительном падеже RU"],
    [draft.document_forms_kk.employee_full_name_genitive_kk, "ФИО в ілік септік KK"],
    [draft.document_forms_ru.position_document_genitive_ru, "Должность RU"],
    [draft.document_forms_kk.position_document_possessive_kk, "Должность KK"],
    [draft.document_org_unit.document_genitive_ru, "Подразделение RU"],
    [draft.document_org_unit.document_genitive_kk, "Подразделение KK"],
    [draft.service_length.new_ru, "Новый стаж RU"], [draft.service_length.new_kk, "Новый стаж KK"],
    [draft.basis.ru, "Основание RU"], [draft.basis.kk, "Основание KK"],
  ]) if (!value.trim()) errors.push(`Заполните: ${label}.`);
  const date = new Date(draft.effective_date + "T00:00:00Z");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(draft.effective_date) || !Number.isFinite(date.getTime()) || date.toISOString().slice(0, 10) !== draft.effective_date || date.getUTCFullYear() < 1900)
    errors.push("Укажите полную дату начала действия.");
  return errors;
}
