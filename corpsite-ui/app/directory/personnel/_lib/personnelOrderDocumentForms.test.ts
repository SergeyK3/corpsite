import { describe, expect, it } from "vitest";
import { resolvePersonnelOrderDocumentForms, resolvePersonnelOrderOrgUnitForms } from "./personnelOrderDocumentForms";

describe("position document forms", () => {
  it('does not calculate a pending unified document form and preserves a manual form',()=>{
    const position={name:'Процедурная медсестра',name_kk:'Емшара мейіргері',document_form_status:'needs_review' as const};
    expect(resolvePersonnelOrderDocumentForms(position).position_document_possessive_kk).toBe('');
    expect(resolvePersonnelOrderDocumentForms(position,{document_forms_kk:{position_document_possessive_kk:'Ручная форма'}}).position_document_possessive_kk).toBe('Ручная форма');
  });
  it("prefers approved catalog forms over historical position defaults while preserving manual input",()=>{
    const position={name:"Историческая должность",document_nominative_ru:"Историческая RU",document_possessive_kk:"Историческая KK",job_nameru:"Заведующий клиническим отделением",job_namekk_doc:"клиникалық бөлімшесінің меңгерушісі"};
    expect(resolvePersonnelOrderDocumentForms(position)).toEqual({position_document_nominative_ru:position.job_nameru,position_document_possessive_kk:position.job_namekk_doc});
    expect(resolvePersonnelOrderDocumentForms(position,{document_forms_kk:{position_document_possessive_kk:"Ручная"}}).position_document_possessive_kk).toBe("Ручная");
  });
  it("uses canonical job fields, preserves saved forms, and ignores a stale employee position", () => {
    const position = { name: "Старое название", name_kk: "мейіргер", job_code: "NURSE", job_nameru: "Медицинская сестра", job_namekk: "Мейіргер", job_namekk_doc: "Согласованная форма KK" };
    expect(resolvePersonnelOrderDocumentForms(position)).toEqual({ position_document_nominative_ru: "Медицинская сестра", position_document_possessive_kk: "Согласованная форма KK" });
    expect(resolvePersonnelOrderDocumentForms(position, { document_forms_kk: { position_document_possessive_kk: "Ручная форма" } }).position_document_possessive_kk).toBe("Ручная форма");
    expect(resolvePersonnelOrderDocumentForms(position, { has_current_assignment: false })).toEqual({ position_document_nominative_ru: "", position_document_possessive_kk: "" });
  });
  it("does not infer a document case from the nominative assignment name", () => {
    expect(resolvePersonnelOrderDocumentForms({ id: 27, name: "Медсестра", name_kk: "мейіргер" })).toEqual({
      position_document_nominative_ru: "медсестра", position_document_possessive_kk: "",
    });
  });
  it("normalizes whitespace/case and falls back to the name for an opaque code", () => {
    expect(resolvePersonnelOrderDocumentForms({ code: "POS_27", name: "  МЕДСЕСТРА  ", name_kk: " мейіргер " }).position_document_possessive_kk).toBe("");
  });
  it("prefers persisted forms to an approved dictionary match", () => {
    expect(resolvePersonnelOrderDocumentForms({ name: "Медсестра" }, {
      document_forms_ru: { position_document_nominative_ru: "Сохранённая RU" },
      document_forms_kk: { position_document_possessive_kk: "Сохранённая KK" },
    })).toEqual({ position_document_nominative_ru: "Сохранённая RU", position_document_possessive_kk: "Сохранённая KK" });
  });
  it("reads explicit position forms but does not invent a specialty or turn name_kk into a document form", () => {
    expect(resolvePersonnelOrderDocumentForms({ name: "Другая должность", document_possessive_kk: "Справочная KK", document_nominative_ru: "Справочная RU" })).toEqual({
      position_document_nominative_ru: "Справочная RU", position_document_possessive_kk: "Справочная KK",
    });
    expect(resolvePersonnelOrderDocumentForms({ name: "Медсестра гинекологии" })).toEqual({
      position_document_nominative_ru: "медсестра гинекологии", position_document_possessive_kk: "",
    });
  });
  it.each([
    ["сестра-хозяйка", "шаруа бикесі", ""],
    ["Рабочий", "жұмысшы", ""],
    ["Бухгалтер", "бухгалтер", ""],
    ["Врач", null, ""],
    ["Медсестра", "  ", ""],
  ])("uses only the supplied catalogue for %s", (name, name_kk, expected) => {
    expect(resolvePersonnelOrderDocumentForms({ name, name_kk }).position_document_possessive_kk).toBe(expected);
  });
  it("uses selected-unit saved forms without calculating a missing case", () => {
    expect(resolvePersonnelOrderOrgUnitForms({name:"Диспансер",name_kk:"Диспансер бөлімшесі"})).toEqual({org_unit_title_ru:"Диспансер",org_unit_document_genitive_kk:""});
    expect(resolvePersonnelOrderOrgUnitForms({name:"Отделение"}).org_unit_document_genitive_kk).toBe("");
    expect(resolvePersonnelOrderOrgUnitForms({name_kk:"Отделение",document_genitive_kk:"Сохранено"}).org_unit_document_genitive_kk).toBe("Сохранено");
  });
});
