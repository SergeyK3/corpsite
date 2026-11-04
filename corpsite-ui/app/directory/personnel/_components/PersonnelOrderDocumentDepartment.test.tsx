import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import PersonnelOrderDocumentItemsForm from "./PersonnelOrderDocumentItemsForm";
import { listPersonnelOrderDocumentItems, patchPersonnelOrderDocumentItem, type PersonnelOrderDetailResponse, type PersonnelOrderDocumentItem } from "../_lib/personnelOrdersApi.client";

vi.mock("@/lib/orgUnitsSelect", () => ({loadOrgUnitSelectOptions: vi.fn(async () => [
  {unit_id: 10, name: "Отдел сотрудника", name_kk: "А бөлімі", document_genitive_kk: "А бөлімінің", group_id: 1},
  {unit_id: 20, name: "Другой отдел", name_kk: "Б бөлімі", document_genitive_kk: "Б бөлімінің", group_id: 99},
  {unit_id: 30, name: "Без перевода", name_kk: null, document_genitive_kk: null, group_id: 100},
])}));
vi.mock("@/app/directory/employees/_lib/api.client", () => ({getEmployees: vi.fn(async () => ({items:[]}))}));
vi.mock("../_lib/personnelOrdersApi.client", async importOriginal => ({
  ...await importOriginal<typeof import("../_lib/personnelOrdersApi.client")>(),
  listPersonnelOrderDocumentItems: vi.fn(), patchPersonnelOrderDocumentItem: vi.fn(),
}));

let saved: PersonnelOrderDocumentItem;
let revision: number;
const detail = {order:{order_id:1,status:"DRAFT",document_revision:1}} as PersonnelOrderDetailResponse;
beforeEach(() => {
  revision=1;
  saved={item_id:11,item_number:1,item_type_code:"HIRE",employee_id:1,employee_name:"Fixture Employee",position_name:"Врач",org_unit_name:"Отдел сотрудника",effective_date:"2026-10-25"};
  vi.mocked(listPersonnelOrderDocumentItems).mockImplementation(async()=>({document_revision:revision,items:[{...saved}]}));
  vi.mocked(patchPersonnelOrderDocumentItem).mockImplementation(async(_order,_item,request)=>{
    saved={...saved,...request.document_subject_context}; revision++;
    return {no_op:false,resulting_document_revision:revision,audit_event_ids:[]};
  });
});
afterEach(()=>{cleanup();vi.clearAllMocks();});

it.each(["Врач","Эксперт"])("keeps %s while selecting a department from another group and reopening",async position=>{
  saved.position_name=position;
  const view=render(<PersonnelOrderDocumentItemsForm detail={detail} onSaved={async()=>{}}/>);
  const select=await screen.findByLabelText("Подразделение 11");
  await screen.findByRole("option",{name:"Другой отдел"});
  expect(screen.getByRole("option",{name:"Без перевода"})).toBeInTheDocument();
  fireEvent.change(select,{target:{value:"20"}});
  expect(screen.getByLabelText("Должность в приказе 11")).toHaveValue(position);
  expect(screen.getByTestId("department-name_ru")).toHaveTextContent("Другой отдел");
  expect(screen.getByTestId("department-name_kk")).toHaveTextContent("Б бөлімі");
  fireEvent.change(screen.getByLabelText("Для текста KK (ілік септік) — вручную"),{target:{value:"Ручная форма KK"}});
  fireEvent.click(screen.getByRole("button",{name:"Сохранить изменения"}));
  await waitFor(()=>expect(screen.getByRole("alert")).toHaveTextContent("Изменения сохранены"));
  expect(patchPersonnelOrderDocumentItem).toHaveBeenCalledWith(1,11,expect.objectContaining({document_subject_context:expect.objectContaining({document_org_unit_id:20,org_unit_name:"Другой отдел",document_org_unit_kk:"Б бөлімі",document_org_unit_genitive_kk:"Ручная форма KK",position_name:position})}));
  view.unmount();
  render(<PersonnelOrderDocumentItemsForm detail={detail} onSaved={async()=>{}}/>);
  await waitFor(()=>expect(screen.getByLabelText("Подразделение 11")).toHaveValue("20"));
  expect(screen.getByLabelText("Для текста KK (ілік септік) — вручную")).toHaveValue("Ручная форма KK");
  expect(screen.getByLabelText("Должность в приказе 11")).toHaveValue(position);
});

it("clears obsolete translations when the next department has no KK form",async()=>{
  render(<PersonnelOrderDocumentItemsForm detail={detail} onSaved={async()=>{}}/>);
  const select=await screen.findByLabelText("Подразделение 11");
  await screen.findByRole("option",{name:"Другой отдел"});
  fireEvent.change(select,{target:{value:"20"}});
  fireEvent.change(select,{target:{value:"30"}});
  expect(screen.getByTestId("department-name_kk")).toHaveTextContent("Не указано");
  expect(screen.getByLabelText("Для текста KK (ілік септік) — вручную")).toHaveValue("");
  expect(screen.getByLabelText("Должность в приказе 11")).toHaveValue("Врач");
});

it("retains manual department edits on save failure",async()=>{
  vi.mocked(patchPersonnelOrderDocumentItem).mockRejectedValueOnce(new Error("fixture failure"));
  render(<PersonnelOrderDocumentItemsForm detail={detail} onSaved={async()=>{}}/>);
  const select=await screen.findByLabelText("Подразделение 11");
  await screen.findByRole("option",{name:"Другой отдел"});
  fireEvent.change(select,{target:{value:"20"}});
  fireEvent.click(screen.getByRole("button",{name:"Сохранить изменения"}));
  await waitFor(()=>expect(screen.getByRole("alert")).toHaveTextContent("Не удалось сохранить"));
  expect(select).toHaveValue("20");
  expect(screen.getByTestId("department-name_ru")).toHaveTextContent("Другой отдел");
});
