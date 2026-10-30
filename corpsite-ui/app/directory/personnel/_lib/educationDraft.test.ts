import { expect, it } from "vitest";
import { emptyEducationDraft, educationErrors, educationOrderPayload, refreshEducationContext, switchEducationSubject, educationLiteralTokens } from "./educationDraft";
import { itemPayloadDraftFromRecord, buildItemPayload } from "./personnelOrderPayload";
import { resolvePersonnelDocumentContext } from "./personnelOrderDocumentContext";

const complete = () => ({ ...emptyEducationDraft(), employee_id: 900001, source_employee_name: "TEST", effective_date: "2026-11-01",
  document_forms_ru: { employee_full_name_genitive_ru: "RU CASE TEST", position_document_genitive_ru: "RU POSITION CASE" },
  document_forms_kk: { employee_full_name_genitive_kk: "KK CASE TEST", position_document_possessive_kk: "KK POSITION CASE" },
  document_org_unit: { unit_id: null, name: "TEST", name_kk: "TEST KK", document_genitive_ru: "RU UNIT CASE", document_genitive_kk: "KK UNIT CASE" },
  education: { level_ru: "TEST level RU", level_kk: "TEST level KK", specialty_ru: "TEST specialty RU", specialty_kk: "TEST specialty KK" },
  education_document: { kind_ru: "TEST document RU", kind_kk: "TEST document KK", number: "TEST-01", issued_at: "2026-06-20" } });

it("round trips every education value and explicit case for both subject modes", () => {
  for (const subject_mode of ["DIRECTORY", "MANUAL"] as const) {
    const payload = educationOrderPayload({ ...complete(), subject_mode });
    expect(educationErrors({ ...payload })).toEqual([]);
    expect(buildItemPayload("EDUCATION_INFORMATION_CHANGE", itemPayloadDraftFromRecord(payload))).toEqual(payload);
    if (subject_mode === "MANUAL") expect(payload.employee_id).toBeNull();
  }
});

it("copies saved cases, keeps missing cases blank and permits authoritative manual corrections", () => {
  const source = { id: 900001, fio: "Тестов Айдар Ерланович", has_current_assignment: true,
    position: { id: 10, name: "Врач TEST", name_kk: "Дәрігер TEST", document_genitive_ru: "СОХРАНЁННАЯ ФОРМА ДОЛЖНОСТИ" },
    org_unit: { unit_id: 20, name: "Отделение TEST", name_kk: "Бөлімше TEST", document_genitive_ru: "СОХРАНЁННАЯ ФОРМА ОТДЕЛЕНИЯ" },
    document_forms_ru: { employee_full_name_genitive_ru: "СОХРАНЁННАЯ ФОРМА ФИО RU" } };
  const context = resolvePersonnelDocumentContext(source);
  const auto = refreshEducationContext(emptyEducationDraft(), context);
  expect(auto.document_forms_ru.employee_full_name_genitive_ru).toBe("СОХРАНЁННАЯ ФОРМА ФИО RU");
  expect(auto.document_forms_ru.position_document_genitive_ru).toBe("СОХРАНЁННАЯ ФОРМА ДОЛЖНОСТИ");
  expect(auto.document_org_unit.document_genitive_ru).toBe("СОХРАНЁННАЯ ФОРМА ОТДЕЛЕНИЯ");
  expect(auto.document_forms_kk.employee_full_name_genitive_kk).toBe("");
  expect(auto.document_forms_kk.position_document_possessive_kk).toBe("");
  const corrected = { ...auto, document_forms_ru: { ...auto.document_forms_ru, employee_full_name_genitive_ru: "РУЧНОЕ ИСПРАВЛЕНИЕ" } };
  expect(refreshEducationContext(corrected, context, context).document_forms_ru.employee_full_name_genitive_ru).toBe("РУЧНОЕ ИСПРАВЛЕНИЕ");
  const manual = switchEducationSubject(complete(), "MANUAL");
  expect(manual.education).toEqual(complete().education);
  expect(manual.document_forms_ru.employee_full_name_genitive_ru).toBe("");
  expect(refreshEducationContext(manual, context)).toBe(manual);
});

it("requires fields used in ID60 and distinguishes issue date from effective date", () => {
  const draft = complete();
  expect(educationErrors({ ...draft, education_document: { ...draft.education_document, issued_at: "2026-02-30" } })).toContain("Укажите полную дату выдачи документа или выберите «Уточнить».");
  expect(educationErrors({ ...draft, education: { ...draft.education, specialty_kk: "" } })).toEqual([]);
  expect(educationLiteralTokens("basis_template_kk", "[мамандық] [құжат түрі] [нөмір] [берілген күні]")).toEqual([
    "education.specialty_kk", "education_document.kind_kk", "education_document.number", "education_document.issued_kk",
  ]);
});
