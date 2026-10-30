import {render,screen,fireEvent,waitFor,cleanup} from "@testing-library/react";
import {afterEach,it,expect,vi} from "vitest";
import {apiFetchJson} from "@/lib/api";
import Manager from "./EducationReferenceManager";
import EmployeeDocumentFormModal from "./personnel/_components/EmployeeDocumentFormModal";
import type {EmployeeDocumentRow} from "./personnel/_lib/documentsApi.client";
vi.mock("@/lib/api",()=>({apiFetchJson:vi.fn()}));
vi.mock("@/lib/orgUnitsSelect",()=>({loadOrgUnitSelectOptions:vi.fn().mockResolvedValue([])}));
vi.mock("./employees/_lib/api.client",()=>({getEmployees:vi.fn().mockResolvedValue({items:[],total:0})}));
afterEach(()=>{cleanup();vi.mocked(apiFetchJson).mockReset();});
const row={code:"TEST",name_ru:"Тест",name_kk:"Сынақ",is_active:true,revision:2,sort_order:10,usage_count:3};
it("edits document kind names through the new API without sending level notes",async()=>{
  vi.mocked(apiFetchJson).mockResolvedValue({items:[row],total:1,schema_ready:true,can_manage:true});
  render(<Manager levels={false}/>);
  fireEvent.click(await screen.findByText("Редактировать TEST"));
  expect(screen.getByLabelText("Код")).toBeDisabled();
  expect(screen.queryByLabelText("Пояснение RU")).toBeNull();
  fireEvent.change(screen.getByLabelText("Название KK"),{target:{value:"Өзгертілді"}});
  fireEvent.click(screen.getByLabelText("Активно"));
  fireEvent.click(screen.getByText("Сохранить"));
  await waitFor(()=>expect(apiFetchJson).toHaveBeenCalledWith("/api/ppr/document-kinds/TEST",{method:"PATCH",body:{name_ru:"Тест",name_kk:"Өзгертілді",is_active:false,sort_order:10,expected_revision:2}}));
});
it("shows bilingual class explanations only for levels and requests filtered values",async()=>{
  vi.mocked(apiFetchJson).mockResolvedValue({items:[{...row,description_ru:"5–9 классы",description_kk:"5–9-сыныптар"}],total:1,schema_ready:true,can_manage:true});
  render(<Manager levels/>);
  expect(await screen.findByRole("cell",{name:/5–9 классы/})).toBeVisible();
  fireEvent.change(screen.getByLabelText("Поиск RU/KK"),{target:{value:"Сынақ"}});
  fireEvent.change(screen.getByLabelText("Статус"),{target:{value:"inactive"}});
  await waitFor(()=>expect(apiFetchJson).toHaveBeenCalledWith("/api/ppr/education-levels",{query:{q:"Сынақ",state:"inactive"}}));
});
it("retains only the saved inactive kind when correcting an old document",async()=>{
  const document={document_id:1,employee_id:1,employee_name:"SYNTHETIC",document_type_id:1,document_kind_id:9,document_kind_code:"ATTESTATION",document_kind_name:"Свидетельство"} as EmployeeDocumentRow;
  const props={open:true,document,documentTypes:[],documentKinds:[{document_kind_id:10,code:"OTHER",name:"Прочее",is_active:false,sort_order:10}],specialties:[],onClose:vi.fn(),onSaved:vi.fn()};
  const {rerender}=render(<EmployeeDocumentFormModal {...props} mode="edit"/>);
  expect(await screen.findByRole("option",{name:"Свидетельство (неактивно)"})).toHaveValue("9");
  expect(screen.queryByRole("option",{name:"Прочее (неактивно)"})).toBeNull();
  rerender(<EmployeeDocumentFormModal {...props} mode="create" document={null}/>);
  expect(screen.queryByRole("option",{name:"Свидетельство (неактивно)"})).toBeNull();
});
