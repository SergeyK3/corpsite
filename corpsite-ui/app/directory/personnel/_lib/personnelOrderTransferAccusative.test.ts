import {expect, it} from "vitest";
import {savedRussianEmployeeNameForm} from "./personnelOrderRussianWording";
import {buildItemPayload, itemPayloadDraftFromRecord} from "./personnelOrderPayload";

it("preserves a manually confirmed female accusative when saving and reopening", () => {
  const source = {document_forms_ru: {employee_full_name_accusative_ru: "Тестову Анну Ивановну"}, to_rate: 0.75};
  const draft = itemPayloadDraftFromRecord(source);
  expect(draft.employee_full_name_accusative_ru).toBe("Тестову Анну Ивановну");
  expect(buildItemPayload("TRANSFER", draft)).toEqual(source);
  draft.employee_full_name_accusative_ru = "Ручная подтверждённая форма";
  expect(itemPayloadDraftFromRecord(buildItemPayload("TRANSFER", draft)).employee_full_name_accusative_ru).toBe("Ручная подтверждённая форма");
  expect(source.document_forms_ru.employee_full_name_accusative_ru).toBe("Тестову Анну Ивановну");
});

it.each([
  {document_forms_ru: {employee_full_name_accusative_ru: "Тестову Анну Ивановну"}},
  {name: {full_name_accusative_ru: "Тестову Анну Ивановну"}},
  {employee_full_name_accusative_ru: "Тестову Анну Ивановну"},
])("uses the existing saved-form contract: %j", source => {
  expect(savedRussianEmployeeNameForm(source, "accusative")).toBe("Тестову Анну Ивановну");
});

it("never derives the accusative from a nominative or dative", () => {
  expect(savedRussianEmployeeNameForm({fio:"Тестова Анна Ивановна", document_forms_ru:{employee_full_name_dative_ru:"Тестовой Анне Ивановне"}}, "accusative")).toBe("");
});
