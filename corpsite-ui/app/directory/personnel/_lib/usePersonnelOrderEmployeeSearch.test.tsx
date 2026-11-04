import * as React from "react";
import {act,cleanup,renderHook,waitFor} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {getEmployee,getEmployees} from "@/app/directory/employees/_lib/api.client";
import type {EmployeeDTO} from "@/app/directory/employees/_lib/types";
import {usePersonnelOrderEmployeeSearch} from "./usePersonnelOrderEmployeeSearch";

vi.mock("@/app/directory/employees/_lib/api.client",()=>({getEmployee:vi.fn(),getEmployees:vi.fn()}));
const employee=(id:string,fio:string)=>({id,fio,status:"active",assignments:[]} as unknown as EmployeeDTO);
const first=employee("2","Сейтказина Синтетическая"),second=employee("3","Акилтаева Синтетическая");
afterEach(()=>{cleanup();vi.resetAllMocks();});
function setup(strict=false){
 vi.mocked(getEmployee).mockResolvedValue(first);
 vi.mocked(getEmployees).mockResolvedValue({items:[second],total:1});
 const onReset=vi.fn(),onSelected=vi.fn();
 const wrapper=({children}:{children:React.ReactNode})=>strict?<React.StrictMode>{children}</React.StrictMode>:<>{children}</>;
 const view=renderHook(()=>usePersonnelOrderEmployeeSearch({enabled:true,initialEmployeeId:2,scopeKey:"1",includeAssignments:true,onReset,onSelected}),{wrapper});
 return {...view,onReset,onSelected};
}
it("loads the default actor under StrictMode and replaces it through direct typing",async()=>{
 const view=setup(true);
 await waitFor(()=>expect(view.result.current.employee?.id).toBe("2"));
 act(()=>view.result.current.input("Ак"));
 expect(view.result.current.employee).toBeNull();expect(view.result.current.query).toBe("Ак");expect(view.onReset).toHaveBeenCalledTimes(1);
 await waitFor(()=>expect(view.result.current.matches).toHaveLength(1));
 expect(getEmployees).toHaveBeenLastCalledWith({q:"Ак",status:"active",limit:10,offset:0});
 vi.mocked(getEmployee).mockResolvedValue(second);
 act(()=>view.result.current.select(second));
 await waitFor(()=>expect(view.result.current.employee?.id).toBe("3"));
 expect(view.result.current.query).toBe(second.fio);expect(view.onSelected).toHaveBeenLastCalledWith(second);
});
it("ignores a late detail response after the user starts another search",async()=>{
 const view=setup();await waitFor(()=>expect(view.result.current.employee?.id).toBe("2"));
 let resolve!:(value:EmployeeDTO)=>void;
 vi.mocked(getEmployee).mockReturnValue(new Promise(done=>{resolve=done;}));
 act(()=>view.result.current.select(second));
 act(()=>view.result.current.input("Другой"));
 await act(async()=>resolve(second));
 expect(view.result.current.query).toBe("Другой");expect(view.result.current.employee).toBeNull();expect(view.onSelected).toHaveBeenCalledTimes(1);
});
it("ignores stale search matches and never restores a cleared default",async()=>{
 const view=setup();await waitFor(()=>expect(view.result.current.employee?.id).toBe("2"));
 let resolve!:(value:{items:EmployeeDTO[];total:number})=>void;
 vi.mocked(getEmployees).mockReturnValueOnce(new Promise(done=>{resolve=done;}));
 act(()=>view.result.current.input("Се"));
 await waitFor(()=>expect(getEmployees).toHaveBeenCalledTimes(1));
 act(()=>view.result.current.input("Ак"));
 await waitFor(()=>expect(view.result.current.matches[0]?.id).toBe("3"));
 await act(async()=>resolve({items:[first],total:1}));
 expect(view.result.current.matches[0]?.id).toBe("3");
 act(()=>view.result.current.clear());view.rerender();
 expect(view.result.current.query).toBe("");expect(view.result.current.employee).toBeNull();expect(getEmployee).toHaveBeenCalledTimes(1);
});


it("keeps an explicit manual snapshot unlinked until the user selects a directory card",async()=>{
 const view=setup();await waitFor(()=>expect(view.result.current.employee?.id).toBe("2"));
 vi.mocked(getEmployees).mockResolvedValue({items:[],total:0});
 act(()=>view.result.current.input("Ручная Фикстура"));
 await waitFor(()=>expect(view.result.current.finished).toBe(true));
 act(()=>view.result.current.confirmManual());view.rerender();
 expect(view.result.current.manualName).toBe("Ручная Фикстура");expect(view.result.current.employee).toBeNull();expect(getEmployee).toHaveBeenCalledTimes(1);
 vi.mocked(getEmployees).mockResolvedValue({items:[second],total:1});
 act(()=>view.result.current.input("Ак"));expect(view.result.current.manualName).toBeNull();
 await waitFor(()=>expect(view.result.current.matches[0]?.id).toBe("3"));
 vi.mocked(getEmployee).mockResolvedValue(second);act(()=>view.result.current.select(second));
 await waitFor(()=>expect(view.result.current.employee?.id).toBe("3"));expect(view.result.current.manualName).toBeNull();
});
