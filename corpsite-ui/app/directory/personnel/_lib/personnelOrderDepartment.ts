
export type DepartmentUnit={unit_id:number|null;name:string;name_kk?:string|null;document_genitive_kk?:string|null;document_genitive_ru?:string|null};
export type DepartmentOverrides=Partial<Record<"name_ru"|"name_kk"|"genitive_ru"|"genitive_kk",string>>;
export type DepartmentDraft={unit:DepartmentUnit|null;overrides:DepartmentOverrides};
export const blankDepartment=():DepartmentDraft=>({unit:null,overrides:{}});
export function departmentFromUnit(unit:(Partial<Omit<DepartmentUnit,"name">>&{name?:string|null})|null|undefined):DepartmentDraft {
 return {unit:unit?{unit_id:unit.unit_id??null,name:unit.name||"",name_kk:unit.name_kk||"",document_genitive_kk:unit.document_genitive_kk||"",document_genitive_ru:unit.document_genitive_ru||""}:null,overrides:{}};
}
export function departmentValues(draft:DepartmentDraft){
 const name_ru=draft.overrides.name_ru??draft.unit?.name??"",name_kk=draft.overrides.name_kk??draft.unit?.name_kk??"";
 return {name_ru,name_kk,genitive_ru:draft.overrides.genitive_ru??(draft.overrides.name_ru!==undefined?"":draft.unit?.document_genitive_ru||""),
  genitive_kk:draft.overrides.genitive_kk??(draft.overrides.name_kk!==undefined?"":draft.unit?.document_genitive_kk||"")};
}
export function departmentSnapshot(draft:DepartmentDraft){
 const values=departmentValues(draft);
 return {unit_id:draft.unit?.unit_id??null,name:values.name_ru,name_kk:values.name_kk,document_genitive_ru:values.genitive_ru,document_genitive_kk:values.genitive_kk,draft};
}
export function departmentFromPayload(payload:Record<string,unknown>):DepartmentDraft {
 const saved=payload.document_org_unit as ReturnType<typeof departmentSnapshot>|undefined;
 if(saved?.draft)return {unit:saved.draft.unit?{...saved.draft.unit}:null,overrides:{...saved.draft.overrides}};
 if(saved)return departmentFromUnit(saved);
 const recipient=payload.allowance_recipient as Record<string,unknown>|undefined;
 if(recipient?.org_unit_ru)return {unit:{unit_id:Number(recipient.org_unit_id)||null,name:String(recipient.org_unit_ru),name_kk:String(payload.org_unit_title_kk||""),document_genitive_kk:String(recipient.org_unit_kk||"")},overrides:recipient.org_unit_genitive_ru?{genitive_ru:String(recipient.org_unit_genitive_ru)}:{}};
 if(payload.source_org_unit_name)return departmentFromUnit({name:String(payload.source_org_unit_name),name_kk:String(payload.org_unit_title_kk||""),document_genitive_kk:String((payload.document_forms_kk as Record<string,unknown>|undefined)?.org_unit_document_genitive_kk||"")});
 return blankDepartment();
}
