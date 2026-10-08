import { expect, it } from "vitest";
import { buildItemPayload, emptyItemPayloadDraft, itemPayloadDraftFromRecord } from "./personnelOrderPayload";
import { PERSONNEL_ORDER_TYPES } from "./personnelOrderLabels";

it.each(PERSONNEL_ORDER_TYPES.filter(type => type !== "COMPOSITE"))("retains edited job forms after JSON save and reopen for %s", type => {
  const draft = { ...emptyItemPayloadDraft(), position_title_ru:"Название RU",position_title_kk:"Название KZ",org_unit_title_kk:"Бөлімше",position_document_nominative_ru: "Ручная RU", position_document_possessive_kk: "Құжат нысаны", org_unit_document_genitive_kk: "Бөлімшенің", org_unit_title_ru: "Подразделение" };
  const saved = JSON.parse(JSON.stringify(buildItemPayload(type, draft)));
  const reopened = itemPayloadDraftFromRecord(saved);
  expect(reopened.position_document_nominative_ru).toBe(draft.position_document_nominative_ru);
  expect(reopened.position_document_possessive_kk).toBe(draft.position_document_possessive_kk);
  expect(reopened.org_unit_document_genitive_kk).toBe(draft.org_unit_document_genitive_kk);
  expect(reopened.org_unit_title_ru).toBe("Подразделение");
  expect(reopened.position_title_ru).toBe(draft.position_title_ru);
  expect(reopened.position_title_kk).toBe(draft.position_title_kk);
  expect(reopened.org_unit_title_kk).toBe(draft.org_unit_title_kk);
});
