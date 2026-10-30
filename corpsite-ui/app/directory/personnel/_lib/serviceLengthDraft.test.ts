import { expect, it } from "vitest";
import { emptyServiceLengthDraft, serviceLengthErrors, serviceLengthOrderPayload, switchServiceLengthSubject, refreshServiceLengthContext } from "./serviceLengthDraft";
import { buildItemPayload, itemPayloadDraftFromRecord } from "./personnelOrderPayload";
import { buildPersonnelOrderPrintDocumentHtml } from "./personnelOrderPrintDocumentHtml";
import type { PersonnelOrderPrintViewModel } from "./personnelOrderPrintViewModel";

const draft = () => ({ ...emptyServiceLengthDraft(), employee_id: 900001, source_employee_name: "TEST", effective_date: "2026-11-01",
  document_forms_ru: { employee_full_name_genitive_ru: "TEST RU", position_document_genitive_ru: "врача" },
  document_forms_kk: { employee_full_name_genitive_kk: "TEST KK", position_document_possessive_kk: "дәрігері" },
  document_org_unit: { unit_id: null, name: "TEST RU", name_kk: "TEST KK", document_genitive_ru: "отделения", document_genitive_kk: "бөлімшесінің" },
  service_length: { new_ru: "10 лет", new_kk: "10 жыл" }, basis: { ru: "Документ TEST-RU", kk: "Құжат TEST-KK" } });

it("round trips independent bilingual grounds and length without category data", () => {
  const source = draft();
  expect(serviceLengthErrors(source)).toEqual([]);
  expect(buildItemPayload("SERVICE_LENGTH_CHANGE", itemPayloadDraftFromRecord(source))).toEqual(source);
  expect(source).not.toHaveProperty("qualification_category");
  expect(source).not.toHaveProperty("medical_specialty");
  expect(serviceLengthErrors({ ...source, basis: { ...source.basis, kk: "" } })).toContain("Заполните: Основание KK.");
  expect(serviceLengthErrors({ ...source, service_length: { ...source.service_length, new_ru: "" } })).toContain("Заполните: Новый стаж RU.");
});

it("accepts a manual subject without employee_id and round trips the entered name and cases", () => {
  const source = { ...draft(), subject_mode: "MANUAL" as const, employee_id: null, source_employee_name: "Ручной Тестовый Сотрудник" };
  expect(serviceLengthErrors(source)).toEqual([]);
  const snapshot = serviceLengthOrderPayload(source);
  expect(snapshot.unresolved_subject?.full_name).toBe(source.source_employee_name);
  expect(snapshot.employee_id).toBeNull();
  const reopened = itemPayloadDraftFromRecord(snapshot);
  expect(reopened.unresolved_subject?.full_name).toBe(source.source_employee_name);
  expect(buildItemPayload("SERVICE_LENGTH_CHANGE", reopened)).toEqual(snapshot);
  expect(serviceLengthErrors({ ...source, source_employee_name: "" })).toContain("Укажите ФИО сотрудника вручную.");
  const context = { employeeId: 1, employeeName: "OTHER", unitId: 1, owners: {}, values: { employee_full_name_genitive_ru: "AUTO" } };
  expect(refreshServiceLengthContext(source, context)).toBe(source);
  const switched = switchServiceLengthSubject(draft(), "MANUAL");
  expect(switched.employee_id).toBeNull();
  expect(switched.source_employee_name).toBe("");
  expect(switched.document_forms_ru.employee_full_name_genitive_ru).toBe("");
  expect(switched.document_forms_kk.employee_full_name_genitive_kk).toBe("");
  expect(switched.service_length).toEqual(source.service_length);
});

it.each(["ru", "kk", "kk-ru"] as const)("prints %s length with one standalone directive per language and saved grounds", language => {
  const model: PersonnelOrderPrintViewModel = {
    orderId: 1, orderNumber: "TEST", orderDate: "2026-10-29", status: "DRAFT", statusMark: "draft",
    organization: { ru: "TEST RU", kk: "TEST KK" }, title: { ru: "Об изменении стажа", kk: "Жұмыс тәжірибесін өзгерту туралы" },
    preamble: { ru: "В связи с изменением сведений, ПРИКАЗЫВАЮ:", kk: "Мәліметтердің өзгеруіне байланысты, БҰЙЫРАМЫН:" },
    closing: null, documentTypeCode: "SERVICE_LENGTH_CHANGE", placeOfIssue: { ru: "TEST", kk: "TEST" },
    items: [{ itemId: 1, itemNumber: 1, itemTypeCode: "SERVICE_LENGTH_CHANGE", employeeId: 900001, employeeName: "TEST", effectiveDate: "2026-11-01",
      context: { itemNumber: 1, itemTypeCode: "SERVICE_LENGTH_CHANGE", employeeName: "TEST", effectiveDate: "2026-11-01", orgUnitName: null, positionName: null, toOrgUnitName: null, toPositionName: null, rate: null, toRate: null, concurrentRate: null, remainingRate: null, totalRate: null, terminationReason: null, payload: {} },
      body: { ru: "Считать стаж составляющим 10 лет.", kk: "Еңбек өтілі 10 жыл болып есептелсін." }, basis: { ru: "Документ TEST-RU", kk: "Құжат TEST-KK" } }],
    basis: [{ ru: "Документ TEST-RU", kk: "Құжат TEST-KK" }], signatory: { position: null, fio: null }, acknowledgements: [], executorName: "TEST",
  };
  const html = buildPersonnelOrderPrintDocumentHtml(model, language);
  if (language !== "kk") { expect(html.match(/ПРИКАЗЫВАЮ:/g)).toHaveLength(1); expect(html).toContain("10 лет"); expect(html).toContain("TEST-RU"); }
  if (language !== "ru") { expect(html.match(/БҰЙЫРАМЫН:/g)).toHaveLength(1); expect(html).toContain("10 жыл"); expect(html).toContain("TEST-KK"); }
  expect(html).not.toContain("Стаж работы ещё не определён");
  expect(html).not.toContain("Жұмыс өтілі әлі анықталмаған");
  expect(model.preamble?.ru).toContain("ПРИКАЗЫВАЮ:");
});
