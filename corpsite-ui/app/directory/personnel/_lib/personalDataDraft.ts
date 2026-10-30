import {emptyServiceLengthDraft,refreshServiceLengthContext,type ServiceLengthDraft} from './serviceLengthDraft';
import type {PersonnelDocumentContext} from './personnelOrderDocumentContext';
export type PersonalDataDraft=Omit<ServiceLengthDraft,'contract'|'service_length'|'basis'>&{
 contract:'personal-data-change-v1';source_position_id?:number|null;source_position_name:string;source_position_name_kk:string;
 source_given_name_ru?:string;source_given_name_kk?:string;
 personal_data:{changes_ru:string;changes_kk:string;new_full_name_ru?:string;new_full_name_kk?:string;new_surname_ru?:string;new_surname_kk?:string;new_given_name_ru?:string;new_given_name_kk?:string};
 identity_document:{kind_ru:string;kind_kk:string;number:string;issued_at:string;issued_at_status?:'KNOWN'|'ABSENT'|'TO_CLARIFY';issuer_ru?:string;issuer_kk?:string};
};
export function emptyPersonalDataDraft():PersonalDataDraft{
 const {contract:_,service_length:__,basis:___,...subject}=emptyServiceLengthDraft();
 return {...subject,contract:'personal-data-change-v1',source_position_name:'',source_position_name_kk:'',personal_data:{changes_ru:'Фамилия',changes_kk:'Тегі'},identity_document:{kind_ru:'удостоверение личности',kind_kk:'жеке куәлігі',number:'',issued_at:'',issued_at_status:'KNOWN'}};
}
export function personalDataDraftFromRecord(source:Partial<PersonalDataDraft>,effectiveDate=''):PersonalDataDraft{
 const blank=emptyPersonalDataDraft();return {...blank,...source,contract:blank.contract,effective_date:source.effective_date||effectiveDate,
 subject_mode:source.unresolved_subject?'MANUAL':source.subject_mode||'DIRECTORY',document_forms_ru:{...blank.document_forms_ru,...source.document_forms_ru},document_forms_kk:{...blank.document_forms_kk,...source.document_forms_kk},document_org_unit:{...blank.document_org_unit,...source.document_org_unit},personal_data:{...blank.personal_data,...source.personal_data},identity_document:{...blank.identity_document,...source.identity_document}};
}
export function refreshPersonalDataContext(draft:PersonalDataDraft,context:PersonnelDocumentContext,previous?:PersonnelDocumentContext|null):PersonalDataDraft{
 if(draft.subject_mode==='MANUAL')return draft;
 const refreshed=refreshServiceLengthContext({...emptyServiceLengthDraft(),...draft,contract:'service-length-change-v1'},context,previous);
 const changed=Boolean(previous?.owners.employee&&previous.owners.position!==context.owners.position);
 const unitChanged=Boolean(previous?.owners.employee&&previous.owners.unit!==context.owners.unit);
 const savedPosition=draft.source_position_id!=null&&!changed;
 const employeeChanged=Boolean(previous?.owners.employee&&previous.owners.employee!==context.owners.employee);
 return {...draft,employee_id:refreshed.employee_id,source_employee_name:refreshed.source_employee_name,source_position_id:changed?null:draft.source_position_id,
 source_given_name_ru:employeeChanged?context.givenNames?.ru:draft.source_given_name_ru||context.givenNames?.ru,
 source_given_name_kk:employeeChanged?context.givenNames?.kk:draft.source_given_name_kk||context.givenNames?.kk,
 document_forms_ru:{...refreshed.document_forms_ru,...(savedPosition?{position_document_genitive_ru:draft.document_forms_ru.position_document_genitive_ru}:{})},document_forms_kk:{...refreshed.document_forms_kk,...(savedPosition?{position_document_possessive_kk:draft.document_forms_kk.position_document_possessive_kk}:{})},
 document_org_unit:draft.document_org_unit.unit_id!=null&&!unitChanged?draft.document_org_unit:refreshed.document_org_unit,
 source_position_name:!savedPosition&&(changed||!draft.source_position_name)?context.values.position_document_nominative_ru||'':draft.source_position_name,
 source_position_name_kk:!savedPosition&&(changed||!draft.source_position_name_kk)?context.values.position_title_kk||'':draft.source_position_name_kk};
}
export function switchPersonalDataSubject(draft:PersonalDataDraft,mode:'DIRECTORY'|'MANUAL'):PersonalDataDraft{
 const blank=emptyPersonalDataDraft();return {...draft,subject_mode:mode,employee_id:null,source_employee_name:'',source_given_name_ru:'',source_given_name_kk:'',unresolved_subject:undefined,source_position_id:null,source_position_name:'',source_position_name_kk:'',document_forms_ru:blank.document_forms_ru,document_forms_kk:blank.document_forms_kk,document_org_unit:blank.document_org_unit};
}
export function personalDataOrderPayload(draft:PersonalDataDraft):PersonalDataDraft{return {...draft,employee_id:draft.subject_mode==='MANUAL'?null:draft.employee_id,unresolved_subject:draft.subject_mode==='MANUAL'?{full_name:draft.source_employee_name}:undefined,identity_document:{...draft.identity_document,issued_at_status:draft.identity_document.issued_at_status||'KNOWN',issued_at:draft.identity_document.issued_at_status&&draft.identity_document.issued_at_status!=='KNOWN'?'':draft.identity_document.issued_at}};}
export function personalDataErrors(draft:PersonalDataDraft):string[]{
 const errors:string[]=[];
 if(draft.subject_mode==='MANUAL'){if(!draft.source_employee_name.trim())errors.push('Укажите ФИО сотрудника вручную.');}
 else if(!Number.isSafeInteger(draft.employee_id)||Number(draft.employee_id)<1)errors.push('Выберите сотрудника.');
 const required={...draft.document_forms_ru,...draft.document_forms_kk,changes_ru:draft.personal_data.changes_ru,changes_kk:draft.personal_data.changes_kk,kind_ru:draft.identity_document.kind_ru,kind_kk:draft.identity_document.kind_kk,number:draft.identity_document.number,unit_ru:draft.document_org_unit.document_genitive_ru,unit_kk:draft.document_org_unit.document_genitive_kk};
 if(Object.values(required).some(value=>!value.trim()))errors.push('Заполните формы ФИО, должности, подразделения, изменения RU/KK и реквизиты удостоверения личности.');
 const status=draft.identity_document.issued_at_status||'KNOWN';
 if(!['KNOWN','ABSENT','TO_CLARIFY'].includes(status))errors.push('Выберите статус даты выдачи удостоверения личности.');
 if(status!=='KNOWN'&&draft.identity_document.issued_at)errors.push('При отсутствии или уточнении даты выдачи оставьте дату пустой.');
 const dates=[['Дата начала действия',draft.effective_date],...(status==='KNOWN'?[['Дата выдачи удостоверения',draft.identity_document.issued_at]]:[])];
 for(const [label,value]of dates){const day=new Date(value+'T00:00:00Z');if(!/^\d{4}-\d{2}-\d{2}$/.test(value)||!Number.isFinite(day.getTime())||day.toISOString().slice(0,10)!==value||day.getUTCFullYear()<1900)errors.push('Укажите полную дату: '+label+'.');}
 return errors;
}
