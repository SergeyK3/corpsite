import {expect,it} from "vitest";
import {resolvePersonnelDocumentContext,mergeDocumentContextValues,refreshCategoryDocumentContext} from "./personnelOrderDocumentContext";
import {emptyCategoryDraft} from "./qualificationCategoryDraft";
const employee={id:"1",fio:"TEST source",has_current_assignment:true,
  document_forms_ru:{employee_full_name_genitive_ru:"Saved genitive RU",employee_full_name_dative_ru:"Saved dative RU"},
  document_forms_kk:{employee_full_name_genitive_kk:"Saved genitive KK"},
  position:{id:2,name:"TEST position",document_genitive_ru:"Saved position RU",document_possessive_kk:"Saved position KK"},
  org_unit:{unit_id:3,name:"TEST unit",name_kk:"TEST unit KK",document_genitive_ru:"Saved unit RU",document_genitive_kk:"Saved unit KK"}};
it("loads explicit forms into one context without inventing a missing case",()=>{
  const ctx=resolvePersonnelDocumentContext(employee);
  expect(ctx.values.employee_full_name_genitive_ru).toBe("Saved genitive RU");expect(ctx.values.employee_full_name_genitive_kk).toBe("Saved genitive KK");
  expect(ctx.values.employee_full_name_dative_kk).toBe("");expect(ctx.values.position_document_genitive_ru).toBe("Saved position RU");
  const category=refreshCategoryDocumentContext(emptyCategoryDraft(),ctx);
  expect(category.document_forms_ru.employee_full_name_genitive_ru).toBe("Saved genitive RU");
  expect(category.document_org_unit.document_genitive_ru).toBe("Saved unit RU");
});
it("preserves manual corrections and clears the relevant forms on a source change",()=>{
  const old=resolvePersonnelDocumentContext(employee);
  const manual={...old.values,employee_full_name_genitive_ru:"Manual name",position_document_genitive_ru:"Manual position"};
  expect(mergeDocumentContextValues(manual,old,old)).toEqual(manual);
  const pos=resolvePersonnelDocumentContext(employee,{id:20,name:"Other position"});
  const changed=mergeDocumentContextValues(manual,pos,old);
  expect(changed.employee_full_name_genitive_ru).toBe("Manual name");expect(changed.position_document_genitive_ru).toBe("");
  const unit=resolvePersonnelDocumentContext(employee,undefined,{unit_id:30,name:"New unit"});
  expect(mergeDocumentContextValues(old.values,unit,old).org_unit_document_genitive_kk).toBe("");
  const other=resolvePersonnelDocumentContext({...employee,id:"2",document_forms_ru:{},document_forms_kk:{}});
  expect(mergeDocumentContextValues(manual,other,old).employee_full_name_genitive_ru).toBe("");
});
it("preserves a manually cleared value on refresh and saved snapshots on reopening",()=>{
  const old=resolvePersonnelDocumentContext(employee);
  expect(mergeDocumentContextValues({...old.values,employee_full_name_genitive_ru:""},old,old).employee_full_name_genitive_ru).toBe("");
  const saved=refreshCategoryDocumentContext(emptyCategoryDraft(),old);saved.document_forms_ru.employee_full_name_genitive_ru="Manual snapshot";
  expect(refreshCategoryDocumentContext(saved,old).document_forms_ru.employee_full_name_genitive_ru).toBe("Manual snapshot");
});
it("keeps a manual clarification typed while the initial employee request is pending",()=>{
  const pending=resolvePersonnelDocumentContext(null),loaded=resolvePersonnelDocumentContext(employee);
  const result=mergeDocumentContextValues({...pending.values,employee_full_name_genitive_ru:"Typed before API response"},loaded,pending);
  expect(result.employee_full_name_genitive_ru).toBe("Typed before API response");
  expect(result.employee_full_name_genitive_kk).toBe("Saved genitive KK");
});
