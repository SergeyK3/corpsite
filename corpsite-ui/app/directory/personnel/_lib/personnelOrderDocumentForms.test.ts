import { describe, expect, it } from "vitest";
import { resolvePersonnelOrderDocumentForms, resolvePersonnelOrderOrgUnitForms } from "./personnelOrderDocumentForms";

describe("position document forms", () => {
  it("resolves the actual assignment API name Медсестра without employee/unit rules", () => {
    expect(resolvePersonnelOrderDocumentForms({ id: 27, name: "Медсестра", name_kk: "мейіргер" })).toEqual({
      position_document_nominative_ru: "медсестра", position_document_possessive_kk: "мейіргері",
    });
  });
  it("normalizes whitespace/case and falls back to the name for an opaque code", () => {
    expect(resolvePersonnelOrderDocumentForms({ code: "POS_27", name: "  МЕДСЕСТРА  ", name_kk: " мейіргер " }).position_document_possessive_kk).toBe("мейіргері");
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
    ["сестра-хозяйка", "шаруа бикесі", "шаруа бикесі"],
    ["Рабочий", "жұмысшы", "жұмысшысы"],
    ["Бухгалтер", "бухгалтер", "бухгалтері"],
    ["Врач", null, ""],
    ["Медсестра", "  ", ""],
  ])("uses only the supplied catalogue for %s", (name, name_kk, expected) => {
    expect(resolvePersonnelOrderDocumentForms({ name, name_kk }).position_document_possessive_kk).toBe(expected);
  });
  it("uses selected-unit saved form, then name_kk calculation, never Russian", () => {
    expect(resolvePersonnelOrderOrgUnitForms({name:"Диспансер",name_kk:"Диспансер бөлімшесі"})).toEqual({org_unit_title_ru:"Диспансер",org_unit_document_genitive_kk:"Диспансер бөлімшесінің"});
    expect(resolvePersonnelOrderOrgUnitForms({name:"Отделение"}).org_unit_document_genitive_kk).toBe("");
    expect(resolvePersonnelOrderOrgUnitForms({name_kk:"Отделение",document_genitive_kk:"Сохранено"}).org_unit_document_genitive_kk).toBe("Сохранено");
  });
});
