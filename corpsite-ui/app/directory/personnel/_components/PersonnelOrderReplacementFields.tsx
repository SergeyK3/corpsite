"use client";
import * as React from "react";
import {getEmployee, getEmployees} from "@/app/directory/employees/_lib/api.client";
import type {EmployeeDTO} from "@/app/directory/employees/_lib/types";
import type {OrgUnitSelectOption} from "@/lib/orgUnitsSelect";
import {calculateKazakhPersonForm} from "../_lib/kazakhDocumentForms";
import {russianEmployeeGenitiveForOrder, savedRussianEmployeeNameForm} from "../_lib/personnelOrderRussianWording";
import {russianReferenceCase} from "../_lib/personnelOrderRussianWording";
import {savedKazakhEmployeeNameForm} from "../_lib/personnelOrderDocumentForms";
import PersonnelOrderTransferFields, {type TransferFields} from "./PersonnelOrderTransferFields";
import {recipientFromAssignment} from "./PersonnelOrderAllowanceRecipient";

export type ReplacementMode = "RATE" | "PAY";
export type ReplacementFields = TransferFields & {
  employee_id?: number; employee_name_ru: string; employee_name_kk: string;
  employee_genitive_ru: string; employee_genitive_kk: string;
  term_type: "" | "NONE" | "DATE" | "UNTIL_RETURN"; end_date: string;
  allowance_percent: string; allowance_basis_ru: string; allowance_basis_kk: string;
};
export type ConcurrentReplacementFields = TransferFields & {employee_name_ru?: string; employee_id?: number; employee_dative_ru: string; employee_dative_kk: string};
export const blankReplacement = (): ReplacementFields => ({position_ru:"",position_kk:"",org_unit_ru:"",org_unit_kk:"",rate:"",basis_ru:"",basis_kk:"",employee_name_ru:"",employee_name_kk:"",employee_genitive_ru:"",employee_genitive_kk:"",term_type:"",end_date:"",allowance_percent:"",allowance_basis_ru:"",allowance_basis_kk:""});
const inputClass = "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900";
export function ReplacementInput({label,value,onChange,type="text"}:{label:string;value:string;onChange:(value:string)=>void;type?:string}) {
  return <label className="block text-sm font-medium">{label}<input aria-label={label} className={inputClass} type={type} step={type==="number"?"any":undefined} value={value} onChange={e=>onChange(e.target.value)}/></label>;
}
export function ReplacementEmployeeSearch({label,value,onEdit,onSelect,includeAssignments=false}:{label:string;value:string;onEdit:(text:string)=>void;onSelect:(employee:EmployeeDTO)=>void;includeAssignments?:boolean}) {
  const [matches,setMatches]=React.useState<EmployeeDTO[]>([]);const [selected,setSelected]=React.useState(false);const [error,setError]=React.useState("");const requestId=React.useRef(0);
  React.useEffect(()=>{let cancelled=false;if(selected || value.trim().length<2){setMatches([]);return;}
    getEmployees({q:value,status:"active",limit:10,offset:0}).then(result=>{if(!cancelled){setMatches(result.items);setError("");}}).catch(()=>{if(!cancelled){setMatches([]);setError("Поиск недоступен. Уточните данные вручную.");}});return()=>{cancelled=true;};
  },[value,selected]);
  return <div><ReplacementInput label={label} value={value} onChange={text=>{++requestId.current;setSelected(false);onEdit(text);}}/>
    {matches.length?<div role="listbox" aria-label={`Результаты: ${label}`}>{matches.map(employee=><button key={employee.id} type="button" role="option" data-employee-id={employee.id} className="block w-full rounded border px-3 py-2 text-left text-sm" onClick={async()=>{const request=++requestId.current;setSelected(true);setMatches([]);const detail=employee.id?await getEmployee(String(employee.id),includeAssignments).catch(()=>employee):employee;if(request===requestId.current)onSelect(detail);}}>{employee.fio} · {employee.position?.name} · {employee.org_unit?.name}</button>)}</div>:null}
    {error?<p role="status" className="text-xs text-amber-700">{error}</p>:null}</div>;
}
export function replacementBlockers(value:ReplacementFields,mode:ReplacementMode,start:string,fixedAllowance=false,serviceArea=false):string[] {
  const labels:Record<string,string>={employee_name_ru:"Замещаемый сотрудник (RU)",employee_name_kk:"Замещаемый сотрудник (KK)",employee_genitive_ru:"ФИО замещаемого в родительном падеже (RU)",employee_genitive_kk:"ФИО замещаемого в родительном падеже (KK)",position_ru:"Замещаемая должность (RU)",position_kk:"Замещаемая должность (KK)",org_unit_ru:"Замещаемое подразделение (RU)",org_unit_kk:"Замещаемое подразделение (KK)",position_genitive_ru:"Замещаемая должность в родительном падеже (RU)",org_unit_genitive_ru:"Замещаемое подразделение в родительном падеже (RU)",term_type:"Срок замещения"};
  if(value.term_type==="DATE")labels.end_date="Дата окончания замещения";
  if(mode==="PAY")Object.assign(labels,{allowance_percent:"Процент доплаты",allowance_basis_ru:"База расчёта доплаты (RU)",allowance_basis_kk:"База расчёта доплаты (KK)"});
  if(serviceArea){
    delete labels.allowance_basis_ru;delete labels.allowance_basis_kk;
    const worker=Boolean(value.employee_id||value.employee_name_ru.trim()||value.employee_name_kk.trim());
    if(!worker&&value.term_type!=="UNTIL_RETURN"){for(const key of Object.keys(labels))if(!['term_type','end_date','allowance_percent'].includes(key))delete labels[key];}
    else {
      for(const key of ['position_ru','position_kk','org_unit_ru','org_unit_kk'])delete labels[key];
      if(!value.position_ru.trim())delete labels.position_genitive_ru;
      if(!value.org_unit_ru.trim())delete labels.org_unit_genitive_ru;
    }
  }
  const missing=Object.entries(labels).filter(([key])=>!String(value[key as keyof ReplacementFields]??"").trim()).map(([,label])=>`Заполните поле «${label}».`);
  if(value.term_type==="DATE" && start && value.end_date && value.end_date<start)missing.push("Дата окончания замещения раньше даты начала.");
  const percent=Number(value.allowance_percent.replace(",","."));
  if(mode==="PAY" && value.allowance_percent && (!Number.isFinite(percent)||percent<=0))missing.push("Процент доплаты должен быть положительным числом.");
  if(mode==="PAY" && fixedAllowance && value.allowance_percent && ![25,50].includes(percent))missing.push("Выберите доплату +25% или +50%.");
  return missing;
}

export default function PersonnelOrderReplacementFields({value,onChange,mode,start,orgUnits,fixedAllowance=false,serviceArea=false}:{value:ReplacementFields;onChange:React.Dispatch<React.SetStateAction<ReplacementFields>>;mode:ReplacementMode;start:string;orgUnits:OrgUnitSelectOption[];fixedAllowance?:boolean;serviceArea?:boolean}) {
  const [selectedEmployee,setSelectedEmployee]=React.useState<EmployeeDTO|null>(null);
  const edited=React.useRef(new Set<keyof ReplacementFields>());
  const update=(key:keyof ReplacementFields,text:string)=>{edited.current.add(key);onChange(current=>({...current,[key]:text}));};
  const fillPlacement=(employee:EmployeeDTO,assignment?:NonNullable<EmployeeDTO['assignments']>[number],clear=false)=>{
    const recipient=clear?null:recipientFromAssignment(employee,assignment);
    const placement:Partial<ReplacementFields>={assignment_id:assignment?.assignment_id,position_id:recipient?.position_id,org_unit_id:recipient?.org_unit_id,position_ru:recipient?.position_ru||'',position_kk:recipient?.position_kk||'',org_unit_ru:recipient?.org_unit_ru||'',org_unit_kk:recipient?.org_unit_kk||'',position_genitive_ru:russianReferenceCase(recipient?.position_ru,'genitive'),org_unit_genitive_ru:recipient?.org_unit_genitive_ru||''};
    onChange(current=>{
      const next={...current,...Object.fromEntries(Object.entries(placement).filter(([key])=>!edited.current.has(key as keyof ReplacementFields)))};
      if(!edited.current.has('position_genitive_ru'))next.position_genitive_ru=russianReferenceCase(next.position_ru,'genitive');
      if(!edited.current.has('org_unit_genitive_ru'))next.org_unit_genitive_ru=russianReferenceCase(next.org_unit_ru,'genitive');
      return next;
    });
  };
  return <section data-testid="replacement-fields" className="space-y-3 sm:col-span-2">
    <h3 className="font-medium">{serviceArea?'Доплата за расширение зоны обслуживания':'Замещение на время отпуска'}</h3>
    <ReplacementEmployeeSearch includeAssignments={serviceArea} label="Замещаемый сотрудник (RU)" value={value.employee_name_ru} onEdit={text=>{setSelectedEmployee(null);onChange(current=>({...current,employee_id:undefined,assignment_id:undefined,employee_name_ru:text}));}} onSelect={employee=>{
      const parts=(employee.fio||"").split(/\s+/);const kkName=[employee.first_name||parts[1],employee.middle_name||parts[2],employee.last_name||parts[0]].filter(Boolean).join(" ");
      const genitive=calculateKazakhPersonForm(employee,"genitive");
      setSelectedEmployee(employee);
      onChange(current=>({...current,employee_id:Number(employee.id)||undefined,employee_name_ru:employee.fio||"",...Object.fromEntries(Object.entries({employee_name_kk:kkName,employee_genitive_ru:russianEmployeeGenitiveForOrder(employee),employee_genitive_kk:serviceArea?(savedKazakhEmployeeNameForm(employee,'genitive')||genitive.value):genitive.needsReview?"":genitive.value}).filter(([key])=>!serviceArea||!edited.current.has(key as keyof ReplacementFields))),...(!serviceArea?{
        position_id:employee.position?.id||undefined,position_ru:employee.position?.job_nameru||employee.position?.name||"",position_kk:employee.position?.document_possessive_kk||employee.position?.job_namekk_doc||employee.position?.job_namekk||employee.position?.name_kk||"",org_unit_id:employee.org_unit?.unit_id||undefined,org_unit_ru:employee.org_unit?.name||"",org_unit_kk:employee.org_unit?.document_genitive_kk||employee.org_unit?.name_kk||"",position_genitive_ru:"",org_unit_genitive_ru:""}:{})}));
      if(serviceArea)fillPlacement(employee,employee.assignments?.length===1?employee.assignments[0]:undefined,employee.assignments?.length!==1);
    }}/>
    {serviceArea&&(selectedEmployee?.assignments?.length||0)>1?<label className="block text-sm">Назначение замещаемого сотрудника<select aria-label="Назначение замещаемого сотрудника" className={inputClass} value={value.assignment_id||''} onChange={e=>{const assignment=selectedEmployee!.assignments!.find(a=>a.assignment_id===Number(e.target.value));fillPlacement(selectedEmployee!,assignment,!assignment);}}><option value="">Выберите назначение</option>{selectedEmployee!.assignments!.map(a=><option key={a.assignment_id} value={a.assignment_id}>{a.position?.job_nameru||a.position?.name} — {a.org_unit?.name} · #{a.assignment_id}</option>)}</select></label>:null}
    {serviceArea&&(value.employee_id||value.employee_name_ru||value.employee_name_kk)?<button type="button" className="rounded border px-3 py-1" onClick={()=>{setSelectedEmployee(null);edited.current.clear();onChange(current=>({...blankReplacement(),allowance_percent:current.allowance_percent,term_type:current.term_type,end_date:current.end_date}));}}>Убрать замещаемого сотрудника</button>:null}
    {([['employee_name_kk','Замещаемый сотрудник (KK)'],['employee_genitive_ru','ФИО замещаемого в родительном падеже (RU)'],['employee_genitive_kk','ФИО замещаемого в родительном падеже (KK)']] as const).map(([key,label])=><ReplacementInput key={key} label={label} value={value[key]} onChange={text=>update(key,text)}/>)}
    {serviceArea?<p className="text-xs">Должность и подразделение замещаемого сотрудника необязательны. При отсутствии этих данных в приказе останется только ФИО.</p>:null}
    <PersonnelOrderTransferFields value={value} onManualEdit={key=>edited.current.add(key)} onChange={next=>onChange(current=>({...current,...(typeof next==="function"?next(current):next)}))} orgUnits={orgUnits} mode="concurrent" showRates={false} showBasis={false} placementLabel="Замещаемая" documentFormsKK autoCaseForms={serviceArea}/>
    <label className="block text-sm font-medium">Срок замещения<select aria-label="Срок замещения" className={inputClass} value={value.term_type} onChange={e=>onChange(current=>({...current,term_type:e.target.value as ReplacementFields['term_type'],end_date:""}))}><option value="">Выберите срок</option>{serviceArea?<option value="NONE">Без указания срока</option>:null}<option value="DATE">До конкретной даты</option><option value="UNTIL_RETURN">До выхода замещаемого работника из отпуска</option></select></label>
    {value.term_type==="DATE"?<ReplacementInput label="Дата окончания замещения" value={value.end_date} type="date" onChange={text=>update('end_date',text)}/>:null}
    {mode==="PAY"?<>
      {fixedAllowance ? <label className="block text-sm font-medium">Доплата<select aria-label="Доплата" required className={inputClass} value={value.allowance_percent} onChange={e=>update('allowance_percent',e.target.value)}><option value="">Выберите доплату</option><option value="25">+25%</option><option value="50">+50%</option></select></label> : <ReplacementInput label="Процент доплаты" value={value.allowance_percent} type="number" onChange={text=>update('allowance_percent',text)}/>}
      {!serviceArea?<><ReplacementInput label="База расчёта доплаты (RU)" value={value.allowance_basis_ru} onChange={text=>update('allowance_basis_ru',text)}/>
      <ReplacementInput label="База расчёта доплаты (KK)" value={value.allowance_basis_kk} onChange={text=>update('allowance_basis_kk',text)}/></>:null}
    </>:null}
    <p className="text-xs">Проверьте падежные формы ФИО, должностей и подразделений на обоих языках; каждое значение можно уточнить вручную.</p>
  </section>;
}

export function prefillReplacingEmployee(employee:EmployeeDTO):Partial<ConcurrentReplacementFields> {
  const kk=calculateKazakhPersonForm(employee,"dative");
  return {employee_id:Number(employee.id)||undefined,employee_name_ru:employee.fio||"",employee_dative_ru:savedRussianEmployeeNameForm(employee,"dative"),employee_dative_kk:kk.needsReview?"":kk.value};
}
