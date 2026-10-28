"use client";
import * as React from "react";
import PersonnelOrderMedicalSpecialtyPicker from "./PersonnelOrderMedicalSpecialtyPicker";
import { categoryValidUntil, type QualificationCategoryDraft } from "../_lib/qualificationCategoryDraft";
import { apiFetchJson } from "@/lib/api";
import { formatThrownError } from "@/lib/i18n";

export default function PersonnelOrderCategoryFields({value,onChange,disabled=false}:{value:QualificationCategoryDraft;onChange:(next:QualificationCategoryDraft)=>void;disabled?:boolean}) {
  const category=value.qualification_category;
  const [categories,setCategories]=React.useState<{code:number;name:string;name_kk:string}[]>([]);
  const [error,setError]=React.useState("");
  const [retry,setRetry]=React.useState(0);
  React.useEffect(()=>{let live=true;setError("");
    apiFetchJson<{items:{code:number;name:string;name_kk:string}[]}>("/directory/medical-qualification-categories")
      .then(result=>{if(live)setCategories(result.items.filter(row=>[2,3,4].includes(row.code)));})
      .catch(exc=>{if(live){setCategories([]);setError(formatThrownError(exc));}});
    return()=>{live=false;};
  },[retry]);
  // Historical level choices acquire classifier labels in the editable copy only.
  React.useEffect(()=>{
    const choice=categories.find(row=>row.code===category.code);
    if(choice&&(category.name_ru!==choice.name||category.name_kk!==choice.name_kk))onChange({...value,qualification_category:{...category,name_ru:choice.name,name_kk:choice.name_kk}});
  },[categories,category,value,onChange]);
  const input=(label:string,text:string,change:(v:string)=>void,type="text",readOnly=false)=><label className="block space-y-1"><span>{label}</span><input aria-label={label} value={text} type={type} disabled={disabled} readOnly={readOnly} onChange={e=>change(e.target.value)} className="block w-full rounded border bg-transparent p-2"/></label>;
  let end="";try{end=categoryValidUntil(category.assigned_at).split('-').reverse().join('.');}catch{}
  return <fieldset disabled={disabled} className="space-y-3 rounded border p-3 sm:col-span-2" data-testid="order-category-fields">
    <legend>Квалификационная категория</legend>
    {input('ФИО в родительном падеже RU',value.document_forms_ru.employee_full_name_genitive_ru,v=>onChange({...value,document_forms_ru:{...value.document_forms_ru,employee_full_name_genitive_ru:v}}))}
    {input('ФИО в ілік септік KK',value.document_forms_kk.employee_full_name_genitive_kk,v=>onChange({...value,document_forms_kk:{...value.document_forms_kk,employee_full_name_genitive_kk:v}}))}
    {input('Должность в родительном падеже RU',value.document_forms_ru.position_document_genitive_ru,v=>onChange({...value,document_forms_ru:{...value.document_forms_ru,position_document_genitive_ru:v}}))}
    {input('Должность в тексте KK',value.document_forms_kk.position_document_possessive_kk,v=>onChange({...value,document_forms_kk:{...value.document_forms_kk,position_document_possessive_kk:v}}))}
    {([['name','Подразделение RU'],['name_kk','Подразделение KK'],['document_genitive_ru','Подразделение в родительном падеже RU'],['document_genitive_kk','Подразделение в ілік септік KK']] as const).map(([key,label])=><React.Fragment key={key}>{input(label,value.document_org_unit[key],v=>onChange({...value,document_org_unit:{...value.document_org_unit,[key]:v}}))}</React.Fragment>)}
    <PersonnelOrderMedicalSpecialtyPicker value={value.medical_specialty} disabled={disabled} onChange={medical_specialty=>onChange({...value,medical_specialty})}/>
    <label className="block">Категория квалификации<select aria-label="Категория квалификации" value={category.code??""} disabled={disabled||!categories.length||!!error} onChange={e=>{
      const choice=categories.find(row=>row.code===Number(e.target.value));
      onChange({...value,contract:"medical-qualification-category-v2",qualification_category:{...category,code:choice?.code??null,name_ru:choice?.name??"",name_kk:choice?.name_kk??""}});
    }} className="ml-2 rounded border bg-transparent p-2"><option value="" disabled>Выберите категорию</option>{categories.map(row=><option key={row.code} value={row.code}>{row.name} / {row.name_kk}</option>)}</select></label>
    {error&&<p role="alert">{error} <button type="button" onClick={()=>setRetry(n=>n+1)}>Повторить загрузку категорий</button></p>}
    {input('Дата присвоения',category.assigned_at,v=>onChange({...value,qualification_category:{...category,assigned_at:v}}),'date')}
    {input('Дата начала действия',value.effective_date||"",v=>onChange({...value,effective_date:v}),'date')}
    {input('Дата окончания категории',end,()=>{},'text',true)}
    <p className="text-xs">Дата присвоения + 5 календарных лет − 1 день. Падежные формы проверьте по документу.</p>
  </fieldset>;
}
