"use client";
import {useEffect,useRef} from 'react';
import PersonnelOrderPositionPicker from './PersonnelOrderPositionPicker';
import {usePersonnelOrderPositions,type DocumentPosition} from '../_lib/personnelOrderPositions';
import {resolvePersonnelOrderDocumentForms} from '../_lib/personnelOrderDocumentForms';
import type {EmployeeDTO} from '@/app/directory/employees/_lib/types';
import {russianReferenceCase} from '../_lib/personnelOrderRussianWording';
import {calculateKazakhPositionPossessive,calculateKazakhOrgUnitGenitive,firstNonEmpty} from '../_lib/kazakhDocumentForms';
export type AllowanceRecipient={assignment_id?:number;position_id?:number;org_unit_id?:number;position_ru:string;position_kk:string;org_unit_ru:string;org_unit_kk:string;position_dative_ru:string;org_unit_genitive_ru:string};
export const blankAllowanceRecipient=():AllowanceRecipient=>({position_ru:'',position_kk:'',org_unit_ru:'',org_unit_kk:'',position_dative_ru:'',org_unit_genitive_ru:''});
export function recipientFromAssignment(employee:EmployeeDTO,assignment?:NonNullable<EmployeeDTO['assignments']>[number]):AllowanceRecipient {
 const position=assignment&&assignment.position_id===employee.position?.id?{...assignment.position,...employee.position}:assignment?.position||employee.position;
 const unit=assignment&&assignment.org_unit_id===employee.org_unit?.unit_id?{...assignment.org_unit,...employee.org_unit}:assignment?.org_unit||employee.org_unit;
 const ru=position?.job_nameru||position?.name||'';const unitRu=unit?.name||'';
 const positionProposal=calculateKazakhPositionPossessive(position?.job_namekk||position?.name_kk);
 const unitProposal=calculateKazakhOrgUnitGenitive(unit?.name_kk);
 return {assignment_id:assignment?.assignment_id,position_id:assignment?.position_id||employee.position?.id||undefined,org_unit_id:assignment?.org_unit_id||employee.org_unit?.unit_id||undefined,
  position_ru:ru,org_unit_ru:unitRu,position_dative_ru:russianReferenceCase(ru,'dative'),org_unit_genitive_ru:russianReferenceCase(unitRu,'genitive'),
  position_kk:position&&'document_form_status' in position&&position.document_form_status==='needs_review'?'':firstNonEmpty(position?.document_possessive_kk,('job_namekk_doc' in (position||{})?(position as {job_namekk_doc?:string}).job_namekk_doc:''),positionProposal.needsReview?'':positionProposal.value),
  org_unit_kk:firstNonEmpty(unit?.document_genitive_kk,unitProposal.needsReview?'':unitProposal.value)};
}
export function recipientBlockers(value:AllowanceRecipient,employee:EmployeeDTO|null,requireUnitCase=true,requireKkPosition=true):string[]{
 const labels:Record<string,string>={position_ru:'Должность получателя (RU)',org_unit_ru:'Подразделение получателя (RU)',position_kk:'Должность получателя (KK)',org_unit_kk:'Подразделение получателя (KK)',org_unit_genitive_ru:'Подразделение получателя для текста (RU)'};
 if(!requireUnitCase)delete labels.org_unit_genitive_ru;
 if(!requireKkPosition)delete labels.position_kk;
 const missing=Object.entries(labels).filter(([key])=>!String(value[key as keyof AllowanceRecipient]||'').trim()).map(([,label])=>`Уточните поле «${label}».`);
 if((employee?.assignments?.length||0)>1&&!value.assignment_id)missing.push('Выберите назначение получателя доплаты.');return missing;
}
export default function PersonnelOrderAllowanceRecipient({employee,value,onChange,sharedDepartment=false}:{employee:EmployeeDTO;value:AllowanceRecipient;onChange:(value:AllowanceRecipient)=>void;sharedDepartment?:boolean}) {
 const catalog=usePersonnelOrderPositions(true);
 const owner=useRef(employee.id),initial=useRef<string|null>(null);
 const chosenPosition=useRef<number|undefined>(value.position_ru?value.position_id:undefined);
 const edited=useRef(new Set<string>());const previous=useRef<AllowanceRecipient|null>(null);
 const assignments=employee.assignments||[];
 useEffect(()=>{
  if(owner.current!==employee.id)return;
  const forms={position_dative_ru:russianReferenceCase(value.position_ru,'dative'),org_unit_genitive_ru:russianReferenceCase(value.org_unit_ru,'genitive')};
  const changes:Partial<AllowanceRecipient>={};
  for(const key of (sharedDepartment?['position_dative_ru']:['position_dative_ru','org_unit_genitive_ru']) as ('position_dative_ru'|'org_unit_genitive_ru')[])if(!edited.current.has(key)&&(!value[key]||value[key]===previous.current?.[key]))changes[key]=forms[key];
  previous.current={...value,...forms};
  if(Object.keys(changes).some(key=>value[key as keyof AllowanceRecipient]!==changes[key as keyof AllowanceRecipient]))onChange({...value,...changes});
 },[employee.id,value.position_ru,value.org_unit_ru]);
 useEffect(()=>{
  const changed=owner.current!==employee.id;
  if(changed){owner.current=employee.id;initial.current=null;edited.current.clear();previous.current=null;chosenPosition.current=undefined;}
  if(initial.current===employee.id)return;
  if(employee.assignments===undefined){if(changed)onChange(blankAllowanceRecipient());return;}
  initial.current=employee.id;
  // A saved document is authoritative on reopen; live assignment details must
  // not overwrite its selected role or manual wording.
  if(!changed&&(value.position_ru||(!sharedDepartment&&value.org_unit_ru)||value.assignment_id))return;
  onChange(assignments.length<=1?recipientFromAssignment(employee,assignments[0]):blankAllowanceRecipient());
 },[employee.id,employee.assignments]);
 const chooseAssignment=(id:string)=>{
  if(Number(id)===value.assignment_id)return;
  edited.current.clear();previous.current=null;chosenPosition.current=undefined;
  const selected=assignments.find(a=>a.assignment_id===Number(id));
  onChange(selected?recipientFromAssignment(employee,selected):blankAllowanceRecipient());
 };
 const choosePosition=(position:DocumentPosition)=>{
  if(position.id===chosenPosition.current)return;
  chosenPosition.current=position.id;
  for(const key of ['position_ru','position_kk','position_dative_ru'])edited.current.delete(key);
  const forms=resolvePersonnelOrderDocumentForms(position);
  onChange({...value,position_id:position.id,position_ru:position.name,position_kk:forms.position_document_possessive_kk,position_dative_ru:russianReferenceCase(position.name,'dative')});
 };
 return <section className="space-y-2 sm:col-span-2" data-testid="allowance-recipient"><h3 className="font-medium">Назначение получателя доплаты</h3>
 <p className="text-xs">Дательная форма должности рассчитывается автоматически. Её можно уточнить вручную для текста приказа.</p>
 {assignments.length>1?<label className="block text-sm">Назначение получателя<select aria-label="Назначение получателя" className="block w-full rounded border p-2" value={value.assignment_id||''} onChange={e=>chooseAssignment(e.target.value)}><option value="">Выберите назначение</option>{assignments.map(a=><option key={a.assignment_id} value={a.assignment_id}>{a.position?.name} — {a.org_unit?.name} · #{a.assignment_id}{a.is_primary?' · основное':''}</option>)}</select></label>:null}
 <label className="block text-sm">Должность получателя (RU)<PersonnelOrderPositionPicker label="Должность получателя (RU)" value={value.position_ru} {...catalog} onSelect={choosePosition} onCustomChange={text=>{edited.current.add('position_ru');onChange({...value,position_ru:text});}}/></label>
 {Object.entries({org_unit_ru:'Подразделение получателя (RU)',position_kk:'Должность получателя (KK)',org_unit_kk:'Подразделение получателя (KK)',position_dative_ru:'Должность получателя в дательном падеже (RU)',org_unit_genitive_ru:'Подразделение получателя для текста (RU)'}).filter(([key])=>!sharedDepartment||!key.startsWith('org_unit')).map(([key,label])=><label key={key} className="block text-sm">{label}<input aria-label={label} className="block w-full rounded border p-2" value={String(value[key as keyof AllowanceRecipient]||'')} onChange={e=>{edited.current.add(key);onChange({...value,[key]:e.target.value});}}/></label>)}
 </section>;
}
