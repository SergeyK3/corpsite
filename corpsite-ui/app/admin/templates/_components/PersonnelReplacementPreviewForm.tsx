"use client";
import {useEffect,useState} from "react";
import {apiFetchJson} from "@/lib/api";
import {loadOrgUnitSelectOptions,type OrgUnitSelectOption} from "@/lib/orgUnitsSelect";
import PersonnelOrderTransferFields from "@/app/directory/personnel/_components/PersonnelOrderTransferFields";
import PersonnelOrderReplacementFields,{ReplacementEmployeeSearch,ReplacementInput,blankReplacement,prefillReplacingEmployee,replacementBlockers,type ConcurrentReplacementFields,type ReplacementFields,type ReplacementMode} from "@/app/directory/personnel/_components/PersonnelOrderReplacementFields";
import type {PersonnelOrderTemplateDraft,PersonnelOrderTemplatePreview} from "../_lib/personnelOrderTemplatesApi.client";

export default function PersonnelReplacementPreviewForm({draft,mode,onPreview}:{draft:PersonnelOrderTemplateDraft;mode:ReplacementMode;onPreview:(value:{previews:Record<'ru'|'kk',PersonnelOrderTemplatePreview>})=>void}) {
  const [units,setUnits]=useState<OrgUnitSelectOption[]>([]);
  useEffect(()=>{let active=true;loadOrgUnitSelectOptions().then(rows=>{if(active)setUnits(rows);}).catch(()=>{});return()=>{active=false;};},[]);
  const [start,setStart]=useState("2026-07-03");
  const [concurrent,setConcurrent]=useState<ConcurrentReplacementFields>({employee_name_ru:"Турымов Алибек Рапхатович",employee_dative_ru:"Турымову Алибеку Рапхатовичу",employee_dative_kk:"Алибек Рапхатович Турымовқа",position_ru:"Врач",position_kk:"дәрігері",org_unit_ru:"Отделение терапии",org_unit_kk:"терапия бөлімшесінің",position_genitive_ru:"врача",org_unit_genitive_ru:"отделения терапии",rate:"0.25",total_rate:"1.25",basis_ru:"личное заявление",basis_kk:"жеке өтініш"});
  const [replacement,setReplacement]=useState<ReplacementFields>({...blankReplacement(),employee_name_ru:"Иванов Иван Иванович",employee_name_kk:"Иван Иванович Иванов",employee_genitive_ru:"Иванова Ивана Ивановича",employee_genitive_kk:"Иван Иванович Ивановтың",position_ru:"Врач",position_kk:"дәрігері",org_unit_ru:"Отделение терапии",org_unit_kk:"терапия бөлімшесінің",position_genitive_ru:"врача",org_unit_genitive_ru:"отделения терапии",term_type:"DATE",end_date:"2026-07-31",allowance_percent:"25",allowance_basis_ru:"должностного оклада замещаемого работника",allowance_basis_kk:"орны алмастырылатын қызметкердің лауазымдық жалақысының"});
  const [busy,setBusy]=useState(false);const [error,setError]=useState("");
  const blockers=replacementBlockers(replacement,mode,start);
  const labels:Record<string,string>={employee_dative_ru:'ФИО замещающего (RU)',employee_dative_kk:'ФИО замещающего (KK)',position_ru:'Дополнительная должность (RU)',position_kk:'Дополнительная должность (KK)',org_unit_ru:'Дополнительное подразделение (RU)',org_unit_kk:'Дополнительное подразделение (KK)',position_genitive_ru:'Дополнительная должность в родительном падеже (RU)',org_unit_genitive_ru:'Дополнительное подразделение в родительном падеже (RU)',basis_ru:'Основание (RU)',basis_kk:'Основание (KK)'};
  for(const[key,label]of Object.entries(labels))if(!String(concurrent[key as keyof ConcurrentReplacementFields]||'').trim())blockers.push('Заполните поле «'+label+'».');
  if(!start)blockers.push('Укажите дату начала замещения.');
  if(mode==='RATE' && (!Number.isFinite(Number(concurrent.rate)) || Number(concurrent.rate)<=0 || !Number.isFinite(Number(concurrent.total_rate)) || Number(concurrent.total_rate)<=Number(concurrent.rate)))blockers.push('Введите дополнительную и подтверждённую суммарную ставки.');
  const change=(key:keyof ConcurrentReplacementFields,value:string)=>setConcurrent(current=>({...current,[key]:value}));
  async function preview(){setBusy(true);setError("");try{
    const data={...concurrent};if(mode==='PAY'){delete data.total_rate;data.rate="";}
    const result=await apiFetchJson<{previews:Record<'ru'|'kk',PersonnelOrderTemplatePreview>;template_version_id:number;revision:number}>(`/admin/personnel-order-templates/${draft.item_type_code}/templates/${draft.template_id}/replacement-preview`,{method:'POST',body:{expected_revision:draft.revision,effective_date:start,concurrent:data,replacement:{...replacement,mode}}});
    if(result.template_version_id!==draft.template_version_id || result.revision!==draft.revision)throw new Error("Предпросмотр другой версии черновика.");onPreview(result);
  }catch(cause){const e=cause as {details?:{detail?:{message?:string}};message?:string};setError(e.details?.detail?.message||e.message||"Не удалось проверить данные замещения.");}finally{setBusy(false);}}
  return <details className="mt-4 rounded-lg border p-3" data-testid="replacement-preview-data"><summary className="cursor-pointer font-medium">Данные замещения для предпросмотра RU/KK</summary><div className="mt-3 space-y-3">
    <p className="text-sm">Показаны тестовые данные. Их изменение и предпросмотр не меняют назначения и оплату сотрудников.</p>
    <ReplacementEmployeeSearch label="Замещающий сотрудник" value={concurrent.employee_name_ru||""} onEdit={text=>change('employee_name_ru',text)} onSelect={employee=>setConcurrent(current=>({...current,...prefillReplacingEmployee(employee)}))}/>
    <ReplacementInput label="ФИО замещающего в дательном падеже (RU)" value={concurrent.employee_dative_ru} onChange={text=>change('employee_dative_ru',text)}/>
    <ReplacementInput label="ФИО замещающего в дательном падеже (KK)" value={concurrent.employee_dative_kk} onChange={text=>change('employee_dative_kk',text)}/>
    <ReplacementInput label="Дата начала замещения" value={start} type="date" onChange={setStart}/>
    <PersonnelOrderTransferFields value={concurrent} onChange={next=>setConcurrent(current=>({...current,...(typeof next==='function'?next(current):next)}))} orgUnits={units} mode="concurrent" showRates={mode==='RATE'} documentFormsKK/>
    <PersonnelOrderReplacementFields value={replacement} onChange={setReplacement} orgUnits={units} start={start} mode={mode}/>
    {blockers.length?<p role="status" className="text-sm text-amber-700">{blockers.join(' ')}</p>:null}
    <button type="button" disabled={busy||blockers.length>0} onClick={()=>void preview()} className="rounded border border-blue-700 px-3 py-2 text-sm text-blue-700 disabled:opacity-50">{busy?'Проверка…':'Проверить сохранённый черновик RU/KK'}</button>
    {error?<p role="alert" className="text-red-700">{error}</p>:null}
  </div></details>;
}
