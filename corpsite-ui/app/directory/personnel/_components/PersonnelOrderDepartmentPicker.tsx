"use client";
import type {OrgUnitSelectOption} from "@/lib/orgUnitsSelect";
import {departmentFromUnit,departmentValues,type DepartmentDraft,type DepartmentOverrides} from "../_lib/personnelOrderDepartment";

export default function PersonnelOrderDepartmentPicker({value,options,onChange,label="Подразделение"}: {
 value:DepartmentDraft;options:OrgUnitSelectOption[];onChange:(draft:DepartmentDraft)=>void;label?:string;
}){
 const fields=departmentValues(value);
 const labels:Record<keyof DepartmentOverrides,string>={name_ru:"Название RU",name_kk:"Название KK",genitive_ru:"Для текста RU (родительный)",genitive_kk:"Для текста KK (ілік септік)"};
 return <section className="space-y-2 rounded border border-zinc-200 p-3 dark:border-zinc-700" data-testid="document-department">
  <label className="block text-sm font-medium">{label}<select aria-label={label} value={value.unit?.unit_id??(value.unit?"saved":"")} onChange={e=>{
   const unit=options.find(row=>row.unit_id===Number(e.target.value));
   onChange({...departmentFromUnit(unit),overrides:unit?.unit_id===value.unit?.unit_id?value.overrides:{}});
  }} className="mt-1 w-full rounded border bg-white p-2 text-sm dark:bg-zinc-950">
   <option value="">Выберите подразделение</option>
   {value.unit && !options.some(row=>row.unit_id===value.unit?.unit_id)?<option value={value.unit.unit_id??"saved"}>{value.unit.name}</option>:null}
   {options.map(unit=><option key={unit.unit_id} value={unit.unit_id}>{unit.name}</option>)}
  </select></label>
  {value.unit&&!value.unit.name_kk?<p role="status" className="text-xs text-amber-700">В справочнике отсутствует казахское название выбранного подразделения. Укажите его в ручном уточнении.</p>:null}
  <dl className="grid gap-x-3 gap-y-1 text-sm sm:grid-cols-[auto_1fr]" aria-label="Автозаполнение подразделения">
   {(Object.keys(labels) as (keyof DepartmentOverrides)[]).map(key=><div key={key} className="contents"><dt className="text-zinc-500">{labels[key]}{value.overrides[key]!==undefined?" · уточнено вручную":""}</dt><dd data-testid={`department-${key}`}>{fields[key]||"Не указано"}</dd></div>)}
  </dl>
  <details open={Object.keys(value.overrides).length>0||undefined} className="text-sm"><summary className="cursor-pointer text-blue-700">Ручное уточнение для текста приказа</summary>
   <p className="mt-2 text-xs text-zinc-500">Уточнения относятся к выбранному подразделению. При выборе другого подразделения они сбрасываются. Пустое поле использует автоматическую форму.</p>
   <div className="mt-2 grid gap-2 sm:grid-cols-2">{(Object.keys(labels) as (keyof DepartmentOverrides)[]).map(key=><label key={key}>{labels[key]} — вручную<input aria-label={`${labels[key]} — вручную`} maxLength={300} value={value.overrides[key]??""} placeholder={fields[key]||""} onChange={e=>{const overrides={...value.overrides};if(e.target.value)overrides[key]=e.target.value;else delete overrides[key];onChange({...value,overrides});}} className="mt-1 w-full rounded border bg-white p-2 dark:bg-zinc-950"/></label>)}</div>
   <button type="button" className="mt-2 text-blue-700" onClick={()=>onChange({...value,overrides:{}})}>Вернуть формы из справочника</button>
  </details>
 </section>;
}
