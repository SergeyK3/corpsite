import * as React from "react";
import {afterEach,expect,it,vi} from "vitest";
import {cleanup,fireEvent,render,screen,waitFor} from "@testing-library/react";
import Page from "./page";
import {apiFetchJson} from "@/lib/api";
import {downloadTableExcel} from "@/lib/tableExport";
vi.mock("@/lib/api",()=>({apiFetchJson:vi.fn()}));
vi.mock("@/lib/tableExport",async original=>({...await original<typeof import("@/lib/tableExport")>(),downloadTableExcel:vi.fn()}));
afterEach(()=>{cleanup();vi.clearAllMocks();});
const rows=Array.from({length:55},(_,n)=>({medical_specialty_id:n+1,name:`Специальность ${n+1}`,name_kk:`Қазақша ${n+1}`,group_id:n%2+1,group_name:`Группа ${n%2+1}`,is_active:n%3!==0}));
function setup(){
 vi.mocked(apiFetchJson).mockImplementation(async(path,opts)=>{
  if(path==="/directory/medical-specialty-groups")return {items:[{group_id:1,name:"Группа 1"},{group_id:2,name:"Группа 2"}]} as never;
  const q=opts?.query??{};
  const filtered=rows.filter(r=>(!q.q||r.name.includes(String(q.q))||r.name_kk.includes(String(q.q)))&&(!q.group_id||r.group_id===Number(q.group_id))&&(!q.is_active||r.is_active));
  return {items:filtered.slice(Number(q.offset??0),Number(q.offset??0)+Number(q.limit??1000)),total:filtered.length} as never;
 });render(<Page/>);
}
it("exports every matching page from zero even when the visible page is not first",async()=>{
 setup();await screen.findByText("Всего: 36");fireEvent.change(screen.getByLabelText("Статус"),{target:{value:"all"}});await screen.findByText("Всего: 55");
 fireEvent.click(screen.getByRole("button",{name:"Далее"}));await screen.findByText("Страница 2 из 3");
 await waitFor(()=>expect(screen.getByRole("button",{name:"Выгрузить в Excel"})).not.toBeDisabled());
 fireEvent.click(screen.getByRole("button",{name:"Выгрузить в Excel"}));await waitFor(()=>expect(downloadTableExcel).toHaveBeenCalled());
 const table=vi.mocked(downloadTableExcel).mock.calls[0][0];expect(table.rows).toHaveLength(55);expect(table.rows[0]).toEqual([1,"Специальность 1","Қазақша 1","Группа 1",false]);expect(screen.getByText("Страница 2 из 3")).toBeInTheDocument();
});
it("searches KK and applies group and status consistently to export",async()=>{
 setup();await screen.findByText("Всего: 36");fireEvent.change(screen.getByLabelText("Поиск по RU / KK"),{target:{value:"Қазақша 1"}});fireEvent.change(screen.getByLabelText("Группа"),{target:{value:"2"}});fireEvent.change(screen.getByLabelText("Статус"),{target:{value:"all"}});
 const expected=rows.filter(r=>r.name_kk.includes("Қазақша 1")&&r.group_id===2);
 await screen.findByText(`Всего: ${expected.length}`);await waitFor(()=>expect(screen.getByRole("button",{name:"Выгрузить в Excel"})).not.toBeDisabled());fireEvent.click(screen.getByRole("button",{name:"Выгрузить в Excel"}));
 await waitFor(()=>expect(downloadTableExcel).toHaveBeenCalled());expect(vi.mocked(downloadTableExcel).mock.calls[0][0].rows.map(r=>r[0])).toEqual(expected.map(r=>r.medical_specialty_id));
});
it("shows a failed API response and disables export instead of claiming an empty directory",async()=>{
 vi.mocked(apiFetchJson).mockRejectedValue(new Error("Сбой API"));render(<Page/>);await screen.findAllByRole("alert");expect(screen.getByRole("button",{name:"Выгрузить в Excel"})).toBeDisabled();
});
