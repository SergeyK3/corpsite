import * as React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import Fields from "./PersonnelOrderCategoryFields";
import { apiFetchJson } from "@/lib/api";
import { categoryDraftErrors, categoryOrderDraftFromRecord, categoryOrderPayload, emptyCategoryOrderDraft, type QualificationCategoryDraft } from "../_lib/qualificationCategoryDraft";

vi.mock("@/lib/api", () => ({ apiFetchJson: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
const categories = [
  { code: 1, name: "Без категории", name_kk: "Санаты жоқ" },
  { code: 2, name: "Вторая категория", name_kk: "Екінші санат" },
  { code: 3, name: "Первая категория", name_kk: "Бірінші санат" },
  { code: 4, name: "Высшая категория", name_kk: "Жоғары санат" },
];
function Harness() {
  const [value, setValue] = React.useState<QualificationCategoryDraft>(() => ({ ...emptyCategoryOrderDraft(), employee_id: 900001, source_employee_name: "TEST",
    document_forms_ru: { employee_full_name_genitive_ru: "TEST RU", position_document_genitive_ru: "TEST RU" },
    document_forms_kk: { employee_full_name_genitive_kk: "TEST KK", position_document_possessive_kk: "TEST KK" },
    document_org_unit: { unit_id: 900002, name: "TEST RU", name_kk: "TEST KK", document_genitive_ru: "TEST RU", document_genitive_kk: "TEST KK" },
  }));
  return <><Fields value={value} onChange={setValue} /><output data-testid="payload">{JSON.stringify(categoryOrderPayload(value))}</output><output data-testid="errors">{categoryDraftErrors(value).join(";")}</output></>;
}
it.each([2, 3, 4].flatMap(code => [false, true].map(specialty => ({ code, specialty }))))("uses the classifier in the order form: $code, specialty=$specialty", async ({ code, specialty }) => {
  vi.mocked(apiFetchJson).mockImplementation(async path => path === "/directory/medical-qualification-categories" ? { items: categories } as never : { items: [{ medical_specialty_id: 900003, name: "TEST Терапия", name_kk: "TEST Терапия", is_active: true }], total: 1 } as never);
  render(<Harness />);
  await screen.findByRole("option", { name: "Вторая категория / Екінші санат" });
  expect(screen.queryByRole("option", { name: /Без категории/ })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Код категории RU")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Код категории KK")).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/Источник кода/)).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Категория квалификации"), { target: { value: String(code) } });
  fireEvent.change(screen.getByLabelText("Дата присвоения"), { target: { value: "2026-06-11" } });
  fireEvent.change(screen.getByLabelText("Дата начала действия"), { target: { value: "2026-07-01" } });
  if (specialty) {
    const picker = screen.getByRole("combobox", { name: "Медицинская специальность (необязательно)" });
    fireEvent.focus(picker);fireEvent.change(picker, { target: { value: "TEST" } });
    fireEvent.click(await screen.findByRole("option", { name: "TEST Терапия / TEST Терапия" }));
  }
  await waitFor(() => expect(screen.getByTestId("errors")).toHaveTextContent(/^$/));
  expect(screen.getByLabelText("Дата окончания категории")).toHaveValue("10.06.2031");
  const payload = JSON.parse(screen.getByTestId("payload").textContent!);
  expect(payload.effective_date).toBe("2026-07-01");
  expect(payload.qualification_category).toEqual({ code, name_ru: categories[code - 1].name, name_kk: categories[code - 1].name_kk, assigned_at: "2026-06-11" });
  expect(payload.medical_specialty).toEqual(specialty ? { medical_specialty_id: 900003, name_ru: "TEST Терапия", name_kk: "TEST Терапия" } : null);
  expect(categoryOrderPayload(categoryOrderDraftFromRecord(payload))).toEqual(payload);
});
it("keeps an independent effective date when opening a historical snapshot", () => {
  const old = { ...emptyCategoryOrderDraft(), effective_date: undefined, contract: undefined, qualification_category: { category: "first" as const, assigned_at: "2026-06-11", category_code_ru: "old", category_code_kk: "old", category_code_source: "old" } };
  const opened = categoryOrderDraftFromRecord(old, "2026-07-01");
  expect(opened.effective_date).toBe("2026-07-01");
  expect(opened.qualification_category.code).toBe(3);
  expect(categoryOrderPayload(opened).qualification_category).not.toHaveProperty("category_code_source");
});
it("requires only the six body grammar forms, classifier choice and separate dates", () => {
  const draft=emptyCategoryOrderDraft();
  draft.employee_id=900001;
  draft.effective_date="2026-07-01";
  draft.qualification_category={...draft.qualification_category,code:3,name_ru:"Первая категория",name_kk:"Бірінші санат",assigned_at:"2026-06-11"};
  draft.document_forms_ru={employee_full_name_genitive_ru:"TEST RU",position_document_genitive_ru:"TEST RU"};
  draft.document_forms_kk={employee_full_name_genitive_kk:"TEST KK",position_document_possessive_kk:"TEST KK"};
  draft.document_org_unit.document_genitive_ru="TEST RU";draft.document_org_unit.document_genitive_kk="TEST KK";
  expect(categoryDraftErrors(draft)).toEqual([]);
  const clearForms: Array<(value:QualificationCategoryDraft)=>void>=[
    value=>{value.document_forms_ru.employee_full_name_genitive_ru="";},value=>{value.document_forms_kk.employee_full_name_genitive_kk="";},
    value=>{value.document_forms_ru.position_document_genitive_ru="";},value=>{value.document_forms_kk.position_document_possessive_kk="";},
    value=>{value.document_org_unit.document_genitive_ru="";},value=>{value.document_org_unit.document_genitive_kk="";},
  ];
  for(const clear of clearForms){
    const invalid=structuredClone(draft);clear(invalid);
    expect(categoryDraftErrors(invalid)).not.toEqual([]);
  }
  const missingDate=structuredClone(draft);missingDate.effective_date="";
  expect(categoryDraftErrors(missingDate)).toContain("Укажите дату начала действия категории.");
});
