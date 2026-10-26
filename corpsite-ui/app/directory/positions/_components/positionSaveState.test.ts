import {expect,it} from "vitest";
import {verifyPositionSaved,positionSaveError,type SavedPosition} from "./positionSaveState";
it('explains the exact position validation reason and status',()=>{
 expect(positionSaveError({status:422,details:{detail:'Confirmed Kazakh document form must not be empty.'}})).toContain('Документная форма KK');
 expect(positionSaveError({status:422,details:{detail:'Unknown position family.'}})).toContain('HTTP 422');
});
it('names rejected fields without echoing raw inputs or technical validation details',()=>{
 const message=positionSaveError({status:422,details:{detail:[{loc:['body','job_code'],msg:'technical error',input:'private input'}]}});
 expect(message).toContain('Общий вид должности');expect(message).not.toContain('private input');expect(message).not.toContain('technical error');
});
const record:SavedPosition={position_id:91,revision:2,name:"Рентген лаборант",category:"medical",name_kk:"ТЕСТ: KK",document_nominative_ru:"рентген лаборант",document_possessive_kk:"ТЕСТ: форма",translation_status:"confirmed",document_form_status:"confirmed",record_kind:"variant",job_code:"CORRECT_TEST",aliases:["Тестовый синоним"]};
it("uses the reread revision and preserves all entered position fields",()=>{
 expect(verifyPositionSaved({...record,expected_revision:1},record,91)).toMatchObject({name:record.name,job_code:record.job_code,expected_revision:2,aliases:record.aliases});
});
it.each(["name_kk","document_nominative_ru","document_possessive_kk","job_code","record_kind","translation_status","document_form_status","category","aliases"] as const)("rejects an unconfirmed %s field",key=>{
 expect(()=>verifyPositionSaved(record,{...record,[key]:key==="aliases"?[]:""},91)).toThrow("не подтвердило все поля");
});
it("rejects the wrong ID or a missing revision",()=>{
 expect(()=>verifyPositionSaved(record,{...record,position_id:92},91)).toThrow("другую запись");
 expect(()=>verifyPositionSaved(record,{...record,revision:undefined},91)).toThrow("ревизию");
});
