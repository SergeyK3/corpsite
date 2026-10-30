import {afterEach,expect,it,vi} from "vitest";
import {getPositions} from "@/app/directory/employees/_lib/api.client";
import {loadPersonnelOrderPositions} from "./personnelOrderPositions";
vi.mock("@/app/directory/employees/_lib/api.client",()=>({getPositions:vi.fn()}));
afterEach(()=>vi.resetAllMocks());
it("loads the whole paginated catalog without employee, unit or used-position filters",async()=>{
 const first=Array.from({length:1000},(_,i)=>({position_id:i+1,name:`Position ${i+1}`}));
 vi.mocked(getPositions).mockResolvedValueOnce({items:first,total:1001}).mockResolvedValueOnce({items:[{position_id:1001,name:"Эксперт",name_kk:"Сарапшы"}],total:1001});
 const result=await loadPersonnelOrderPositions();
 expect(result).toHaveLength(1001);expect(result[1000]).toEqual(expect.objectContaining({id:1001,name:"Эксперт"}));
 expect(getPositions).toHaveBeenNthCalledWith(1,{limit:1000,offset:0});expect(getPositions).toHaveBeenNthCalledWith(2,{limit:1000,offset:1000});
});
it("keeps exact variants separate and clears unconfirmed translations",async()=>{
 vi.mocked(getPositions).mockResolvedValue({items:[{position_id:1,name:"Эксперт",name_kk:"старое",translation_status:"needs_review",document_form_status:"needs_review",document_possessive_kk:"старое"},{position_id:2,name:"Эксперт",name_kk:"Сарапшы"}],total:2});
 const result=await loadPersonnelOrderPositions();expect(result.map(p=>p.id)).toEqual([1,2]);expect(result[0].name_kk).toBeNull();expect(result[0].document_possessive_kk).toBeNull();
});
