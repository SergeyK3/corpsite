"use client";
import {useEffect,useRef} from 'react';
import type {EmployeeDTO} from '@/app/directory/employees/_lib/types';
import {russianReferenceCase} from '../_lib/personnelOrderRussianWording';
import {calculateKazakhPositionPossessive,calculateKazakhOrgUnitGenitive,firstNonEmpty} from '../_lib/kazakhDocumentForms';
export type AllowanceRecipient={assignment_id?:number;position_id?:number;org_unit_id?:number;position_ru:string;position_kk:string;org_unit_ru:string;org_unit_kk:string;position_dative_ru:string;org_unit_genitive_ru:string};
export const blankAllowanceRecipient=():AllowanceRecipient=>({position_ru:'',position_kk:'',org_unit_ru:'',org_unit_kk:'',position_dative_ru:'',org_unit_genitive_ru:''});
export function recipientFromAssignment(employee:EmployeeDTO,assignment?:NonNullable<EmployeeDTO['assignments']>[number]):AllowanceRecipient {
 const position=assignment&&assignment.position_id===employee.position?.id?{...assignment.position,...employee.position}:assignment?.position||employee.position;
 const unit=assignment&&assignment.org_unit_id===employee.org_unit?.unit_id?{...assignment.org_unit,...employee.org_unit}:assignment?.org_unit||employee.org_unit;
 const ru=position?.job_nameru||position?.name||'';const unitRu=unit?.name||'';
 return {assignment_id:assignment?.assignment_id,position_id:assignment?.position_id||employee.position?.id||undefined,org_unit_id:assignment?.org_unit_id||employee.org_unit?.unit_id||undefined,
  position_ru:ru,org_unit_ru:unitRu,position_dative_ru:russianReferenceCase(ru,'dative'),org_unit_genitive_ru:russianReferenceCase(unitRu,'genitive'),
  position_kk:firstNonEmpty(position?.document_possessive_kk,('job_namekk_doc' in (position||{})?(position as {job_namekk_doc?:string}).job_namekk_doc:''),calculateKazakhPositionPossessive(position?.job_namekk||position?.name_kk).value),
  org_unit_kk:firstNonEmpty(unit?.document_genitive_kk,calculateKazakhOrgUnitGenitive(unit?.name_kk).value)};
}
export function recipientBlockers(value:AllowanceRecipient,employee:EmployeeDTO|null,requireUnitCase=true,requireKkPosition=true):string[]{
 const labels:Record<string,string>={position_ru:'Должность получателя (RU)',org_unit_ru:'Подразделение получателя (RU)',position_kk:'Должность получателя (KK)',org_unit_kk:'Подразделение получателя (KK)',org_unit_genitive_ru:'Подразделение получателя для текста (RU)'};
 if(!requireUnitCase)delete labels.org_unit_genitive_ru;
 if(!requireKkPosition)delete labels.position_kk;
 const missing=Object.entries(labels).filter(([key])=>!String(value[key as keyof AllowanceRecipient]||'').trim()).map(([,label])=>`Уточните поле «${label}».`);
 if((employee?.assignments?.length||0)>1&&!value.assignment_id)missing.push('Выберите назначение получателя доплаты.');return missing;
}
export default function PersonnelOrderAllowanceRecipient({employee,value,onChange}:{employee:EmployeeDTO;value:AllowanceRecipient;onChange:(value:AllowanceRecipient)=>void}) {
 const initial=useRef<string|null|undefined>(undefined);const assignments=employee.assignments||[];
 const edited=useRef(new Set<string>());const previous=useRef<AllowanceRecipient|null>(null);
 useEffect(()=>{
  const forms={position_dative_ru:russianReferenceCase(value.position_ru,'dative'),org_unit_genitive_ru:russianReferenceCase(value.org_unit_ru,'genitive')};
  const changes:Partial<AllowanceRecipient>={};
  for(const key of ['position_dative_ru','org_unit_genitive_ru'] as const)if(!edited.current.has(key)&&(!value[key]||value[key]===previous.current?.[key]))changes[key]=forms[key];
  previous.current={...value,...forms};
  if(Object.keys(changes).some(key=>value[key as keyof AllowanceRecipient]!==changes[key as keyof AllowanceRecipient]))onChange({...value,...changes});
 },[value.position_ru,value.org_unit_ru]);
 useEffect(()=>{if(employee.assignments===undefined||initial.current===employee.id)return;initial.current=employee.id;
  const next=assignments.length<=1?recipientFromAssignment(employee,assignments[0]):blankAllowanceRecipient();
  for(const key of edited.current)(next as unknown as Record<string,unknown>)[key]=value[key as keyof AllowanceRecipient];
  onChange(next);
 },[employee.id,assignments]);
 const chooseAssignment=(id:string)=>{if(Number(id)===value.assignment_id)return;const selected=assignments.find(a=>a.assignment_id===Number(id));const next=selected?recipientFromAssignment(employee,selected):blankAllowanceRecipient();for(const key of edited.current)if(selected)(next as unknown as Record<string,unknown>)[key]=value[key as keyof AllowanceRecipient];onChange(next);};
 return <section className="space-y-2 sm:col-span-2" data-testid="allowance-recipient"><h3 className="font-medium">Назначение получателя доплаты</h3>
 <p className="text-xs">Дательная форма должности рассчитывается автоматически и не требует подтверждения. Ручное уточнение необязательно; если форму определить невозможно, в тексте останется только ФИО получателя.</p>
 {assignments.length>1?<label className="block text-sm">Назначение получателя<select aria-label="Назначение получателя" className="block w-full rounded border p-2" value={value.assignment_id||''} onChange={e=>chooseAssignment(e.target.value)}><option value="">Выберите назначение</option>{assignments.map(a=><option key={a.assignment_id} value={a.assignment_id}>{a.position?.name} — {a.org_unit?.name} · #{a.assignment_id}{a.is_primary?' · Основное':''}</option>)}</select></label>:null}
 {Object.entries({position_ru:'Должность получателя (RU)',org_unit_ru:'Подразделение получателя (RU)',position_kk:'Должность получателя (KK)',org_unit_kk:'Подразделение получателя (KK)',position_dative_ru:'Должность получателя в дательном падеже (RU)',org_unit_genitive_ru:'Подразделение получателя для текста (RU)'}).map(([key,label])=><label key={key} className="block text-sm">{label}<input aria-label={label} className="block w-full rounded border p-2" value={String(value[key as keyof AllowanceRecipient]||'')} onChange={e=>{edited.current.add(key);onChange({...value,[key]:e.target.value});}}/></label>)}
 </section>;
}
