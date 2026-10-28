import type { QualificationCategoryDraft } from "./qualificationCategoryDraft";
import { savedRussianEmployeeNameForm } from "./personnelOrderRussianWording";
import { savedKazakhEmployeeNameForm } from "./personnelOrderDocumentForms";

const record = (v: unknown): Record<string, unknown> => v && typeof v === "object" ? v as Record<string, unknown> : {};
const text = (...vs: unknown[]) => vs.find((v): v is string => typeof v === "string" && Boolean(v.trim()))?.trim() || "";
export type PersonnelDocumentContext = {employeeId: number | null; unitId:number|null; employeeName: string; owners: Record<string,string>; values: Record<string,string>};

/** A source change invalidates that entity's forms. Missing cases stay blank. */
export function resolvePersonnelDocumentContext(employee: unknown, selectedPosition?: unknown, selectedUnit?: unknown): PersonnelDocumentContext {
  const e=record(employee), ep=record(e.position), eu=record(e.org_unit);
  const p=e.has_current_assignment===false && selectedPosition===undefined ? {} : record(selectedPosition===undefined?e.position:selectedPosition);
  const u=e.has_current_assignment===false && selectedUnit===undefined ? {} : record(selectedUnit===undefined?e.org_unit:selectedUnit);
  const ru=record(e.document_forms_ru), kk=record(e.document_forms_kk);
  const samePosition=e.has_current_assignment!==false && (selectedPosition===undefined || p.id===ep.id);
  const sameUnit=e.has_current_assignment!==false && (selectedUnit===undefined || u.unit_id===eu.unit_id);
  const owner=String(e.id??e.person_id??e.fio??"");
  const nominal=text(p.name);
  return {employeeId:Number(e.id)||null,unitId:Number(u.unit_id)||null,employeeName:text(e.fio,e.full_name),owners:{employee:owner,position:owner+":"+String(p.id??p.name??""),unit:owner+":"+String(u.unit_id??u.name??"")},values:{
    employee_full_name_dative_ru:savedRussianEmployeeNameForm(e,"dative"),
    employee_full_name_genitive_ru:savedRussianEmployeeNameForm(e,"genitive"),
    employee_full_name_accusative_ru:savedRussianEmployeeNameForm(e,"accusative"),
    employee_full_name_dative_kk:savedKazakhEmployeeNameForm(e,"dative"),
    employee_full_name_genitive_kk:savedKazakhEmployeeNameForm(e,"genitive"),
    position_document_nominative_ru:text(samePosition?ru.position_document_nominative_ru:null,p.job_nameru,p.document_nominative_ru,nominal?nominal[0].toLocaleLowerCase("ru-RU")+nominal.slice(1):""),
    position_document_genitive_ru:text(selectedPosition!==undefined?p.document_genitive_ru:null,samePosition?ru.position_document_genitive_ru:null,p.document_genitive_ru),
    position_document_possessive_kk:text(samePosition?kk.position_document_possessive_kk:null,p.document_form_status==="needs_review"?null:p.job_namekk_doc,p.document_form_status==="needs_review"?null:p.document_possessive_kk),
    org_unit_title_ru:text(u.name),org_unit_title_kk:text(u.name_kk),
    org_unit_document_genitive_ru:text(selectedUnit!==undefined?u.document_genitive_ru:null,sameUnit?ru.org_unit_document_genitive_ru:null,u.document_genitive_ru),
    org_unit_document_genitive_kk:text(selectedUnit!==undefined?u.document_genitive_kk:null,sameUnit?kk.org_unit_document_genitive_kk:null,u.document_genitive_kk),
  }};
}

export function mergeDocumentContextValues(current: Record<string,unknown>, next: PersonnelDocumentContext, previous?: PersonnelDocumentContext | null): Record<string,string> {
  const out:Record<string,string>={};
  for(const [key,value] of Object.entries(next.values)) {
    const group=key.startsWith("employee_")?"employee":key.startsWith("position_")?"position":"unit";
    const sourceChanged=previous && previous.owners.employee!=="" && previous.owners[group]!==next.owners[group];
    const old=typeof current[key]==="string" ? current[key] as string : undefined;
    out[key]=sourceChanged || old===undefined || (previous ? old===previous.values[key] : !old) ? value : old;
  }
  return out;
}

export function refreshCategoryDocumentContext(draft: QualificationCategoryDraft, context: PersonnelDocumentContext, previous?: PersonnelDocumentContext | null): QualificationCategoryDraft {
  const values=mergeDocumentContextValues({...draft.document_forms_ru,...draft.document_forms_kk,
    org_unit_title_ru:draft.document_org_unit.name,org_unit_title_kk:draft.document_org_unit.name_kk,
    org_unit_document_genitive_ru:draft.document_org_unit.document_genitive_ru,org_unit_document_genitive_kk:draft.document_org_unit.document_genitive_kk},context,previous);
  return {...draft,employee_id:context.employeeId,source_employee_name:context.employeeName,
    document_forms_ru:{employee_full_name_genitive_ru:values.employee_full_name_genitive_ru,position_document_genitive_ru:values.position_document_genitive_ru},
    document_forms_kk:{employee_full_name_genitive_kk:values.employee_full_name_genitive_kk,position_document_possessive_kk:values.position_document_possessive_kk},
    document_org_unit:{...draft.document_org_unit,unit_id:context.unitId,name:values.org_unit_title_ru,name_kk:values.org_unit_title_kk,
      document_genitive_ru:values.org_unit_document_genitive_ru,document_genitive_kk:values.org_unit_document_genitive_kk}};
}
