import {expect,it} from "vitest";
import type {EmployeeDTO} from "@/app/directory/employees/_lib/types";
import {recallEmployeePrefill} from "./personnelOrderRecallPrefill";

const employee={id:"77",fio:"Мусабеков Арман Ерланович",has_current_assignment:true,
 position:{id:6,name:"Врач",job_nameru:"врач",job_namekk:"дәрігер",job_namekk_doc:"дәрігері"},
 org_unit:{unit_id:59,name:"Терапия",name_kk:"Терапия",document_genitive_kk:"Терапия бөлімшесінің"}} as EmployeeDTO;
it("uses the exact normalized profession titles and the assignment unit for a mapped department head",()=>{
 const result=recallEmployeePrefill({...employee,position:{id:71,name:"Заведующий отделением химиотерапии 1",name_kk:"№ 1 химиотерапия бөлімшесінің меңгерушісі",document_nominative_ru:"Историческая форма",job_code:"CLINICAL_DEPARTMENT_HEAD",job_nameru:"Заведующий клиническим отделением",job_namekk:"Клиникалық бөлімше меңгерушісі",job_namekk_doc:"клиникалық бөлімшесінің меңгерушісі"},org_unit:{unit_id:45,name:"Химиотерапия 1",name_kk:"№1 химиотерапия бөлімшесі"}} as EmployeeDTO);
 expect(result.positionRu).toBe("Заведующий клиническим отделением");expect(result.positionKk).toBe("Клиникалық бөлімше меңгерушісі");expect(result.unitKk).toBe("№1 химиотерапия бөлімшесі");
});
it("uses existing case suggestions and nominative bilingual placement for recall",()=>{
 const result=recallEmployeePrefill(employee);
 expect(result.genitiveRu).toBe("Мусабекова Армана Ерлановича");
 expect(result.genitiveKk).toBe("Арман Ерланович Мусабековтің");
 expect(result.basisRu).toBe("Докладная записка и личное согласие Мусабекова Армана Ерлановича");
 expect(result.basisKk).toBe("Баяндау хат және Арман Ерланович Мусабековтің жеке келісімі");
 expect(result.positionKk).toBe("дәрігер");expect(result.unitKk).toBe("Терапия");
});
it("prefers explicitly saved case forms",()=>{
 const result=recallEmployeePrefill({...employee,document_forms_ru:{employee_full_name_genitive_ru:"Сохранённая RU форма"},document_forms_kk:{employee_full_name_genitive_kk:"Сақталған KZ нысаны"}} as EmployeeDTO);
 expect(result.basisRu).toContain("Сохранённая RU форма");expect(result.basisKk).toContain("Сақталған KZ нысаны");
 expect(result.suggestedRu).toBe(false);expect(result.suggestedKk).toBe(false);
});
it("leaves unavailable case forms empty instead of using the nominative name",()=>{
 const result=recallEmployeePrefill({...employee,fio:"Неизвестный",last_name:undefined,first_name:undefined,middle_name:undefined});
 expect(result.genitiveRu).toBe("");expect(result.genitiveKk).toBe("");expect(result.basisRu).toBe("");expect(result.basisKk).toBe("");
});
it("does not reuse stale placement when the directory explicitly reports no assignment",()=>{
 const result=recallEmployeePrefill({...employee,has_current_assignment:false});
 expect(result.positionRu).toBe("");expect(result.positionKk).toBe("");expect(result.unitRu).toBe("");expect(result.unitKk).toBe("");
});
