import { describe, it, expect } from "vitest";
import { CATEGORY_LEVELS, categoryValidUntil, emptyCategoryDraft, generateCategoryDraft, serializeCategoryDraft, restoreCategoryDraft } from "./qualificationCategoryDraft";

export function fixture() {
  const draft = emptyCategoryDraft();
  return { ...draft, employee_id: 900001, source_employee_name: "Тестов Айдар Ерланович",
    document_forms_ru: { employee_full_name_genitive_ru: "Тестова Айдара Ерлановича", position_document_genitive_ru: "врача-терапевта" },
    document_forms_kk: { employee_full_name_genitive_kk: "Айдар Ерланұлы Тестовтың", position_document_possessive_kk: "дәрігер-терапевті" },
    document_org_unit: { unit_id: 900002, name: "Тестовое отделение терапии", name_kk: "Тестілік терапия бөлімшесі", document_genitive_ru: "тестового отделения терапии", document_genitive_kk: "Тестілік терапия бөлімшесінің" },
    medical_specialty: { medical_specialty_id: 900003, name_ru: "Терапия", name_kk: "Терапия" },
    qualification_category: { category: "highest" as const, assigned_at: "2026-06-11", category_code_ru: "7.2 (Р)", category_code_kk: "7.2 (R)", category_code_source: "TEST сертификат № TEST-01 от 11.06.2026" } };
}

describe("isolated qualification-category draft", () => {
  it.each([["2026-06-11","2031-06-10"],["2024-02-29","2029-02-27"],["2023-03-01","2028-02-29"],["2026-01-01","2030-12-31"]])("calendar expiry %s → %s", (start,end) => expect(categoryValidUntil(start)).toBe(end));
  it.each(["2026-02-30","2026-02-29","2026-13-01","", "11.06.2026"])("rejects invalid date %s", value => expect(() => categoryValidUntil(value)).toThrow());
  it("renders the requested language ordering and keeps code distinct from level", () => {
    const text = generateCategoryDraft(fixture());
    expect(text.body_template_ru).toBe('С 11.06.2026 категория врача-терапевта («Терапия») тестового отделения терапии Тестова Айдара Ерлановича будет считаться 7.2 (Р) „высшей“ до 10.06.2031.');
    expect(text.body_template_kk).toBe('2026 жылғы 11 маусымнан бастап Тестілік терапия бөлімшесінің дәрігер-терапевті («Терапия») Айдар Ерланұлы Тестовтың санаты 7.2 (R) „жоғары“ 2031 жылғы 10 маусымға дейін болып есептелсін.');
    expect(text.body_template_ru + text.body_template_kk).not.toContain("{{");
  });
  it.each(Object.keys(CATEGORY_LEVELS))("round trips %s, snapshots and both source/rendered texts", category => {
    const draft=fixture(); draft.qualification_category.category=category as "highest";
    const raw=serializeCategoryDraft(draft), reopened=restoreCategoryDraft(raw);
    expect(reopened).toEqual(draft); expect(generateCategoryDraft(reopened)).toEqual(generateCategoryDraft(draft));
    expect(JSON.parse(raw).texts.body_template_kk).toContain("{{employee.full_name_genitive_kk}}");
  });
  it("does not default a code from level or specialty; rejects no-category and missing certificate", () => {
    const draft=fixture(); draft.qualification_category.category_code_ru="";
    expect(() => generateCategoryDraft(draft)).toThrow("Код категории RU");
    draft.qualification_category.category_code_ru="7.2 (Р)"; draft.qualification_category.category="none" as "highest";
    expect(() => generateCategoryDraft(draft)).toThrow("Выберите высшую");
    draft.qualification_category.category="highest"; draft.qualification_category.category_code_source="";
    expect(() => generateCategoryDraft(draft)).toThrow("Источник кода");
  });
  it("rejects specialty without id or KK; keeps explicit grammatical forms required", () => {
    const draft=fixture(); draft.medical_specialty.name_kk="";
    expect(() => generateCategoryDraft(draft)).toThrow("специальность");
    draft.medical_specialty.name_kk="Терапия"; draft.document_forms_kk.employee_full_name_genitive_kk="";
    expect(() => generateCategoryDraft(draft)).toThrow("ФИО в ілік");
  });
  it("rejects altered expiry or texts on reopen", () => {
    const stored=JSON.parse(serializeCategoryDraft(fixture())); stored.rendered.valid_until="2099-01-01";
    expect(() => restoreCategoryDraft(JSON.stringify(stored))).toThrow("изменены");
    const texts=JSON.parse(serializeCategoryDraft(fixture())); texts.texts.body_template_ru="Changed";
    expect(() => restoreCategoryDraft(JSON.stringify(texts))).toThrow("изменены");
  });
});
