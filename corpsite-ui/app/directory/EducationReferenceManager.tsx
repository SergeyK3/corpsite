"use client";
import {useEffect,useState} from "react";
import {apiFetchJson} from "@/lib/api";
import {formatThrownError} from "@/lib/i18n";
type ReferenceValue={code:string;name_ru:string;name_kk:string;description_ru?:string;description_kk?:string;sort_order:number;is_active:boolean;revision:number;usage_count:number};
type ReferenceList={items:ReferenceValue[];total:number;schema_ready:boolean};

const blank={code:"",name_ru:"",name_kk:"",sort_order:0,is_active:true,description_ru:"",description_kk:""};
const input="rounded border bg-transparent p-2";
export default function EducationReferenceManager({levels}:{levels:boolean}){
  const API=levels?"/api/ppr/education-levels":"/api/ppr/document-kinds";
  const [list,setList]=useState<ReferenceList & {can_manage?:boolean}>({items:[],total:0,schema_ready:false});
  const [query,setQuery]=useState("");const [state,setState]=useState("all");const [refresh,setRefresh]=useState(0);
  const [editing,setEditing]=useState<ReferenceValue|null|undefined>(undefined);const [form,setForm]=useState(blank);
  const [error,setError]=useState("");const [busy,setBusy]=useState(false);
  useEffect(()=>{let live=true;void apiFetchJson<typeof list>(API,{query:{q:query,state}}).then(r=>{if(live){setList(r);setError("");}}).catch(e=>{if(live)setError(formatThrownError(e));});return()=>{live=false;};},[query,state,refresh]);
  function open(row:ReferenceValue|null){setEditing(row);setForm(row?{code:row.code,name_ru:row.name_ru,name_kk:row.name_kk??"",sort_order:row.sort_order,is_active:row.is_active,description_ru:row.description_ru??"",description_kk:row.description_kk??""}:blank);setError("");}
  async function save(){setBusy(true);setError("");try{
    const {code,description_ru,description_kk,...common}=form;
    const values=levels?{...common,description_ru,description_kk}:common;
    await apiFetchJson(API+(editing?'/'+encodeURIComponent(editing.code):''),{method:editing?'PATCH':'POST',body:editing?{...values,expected_revision:editing.revision}:{code,...values}});
    setEditing(undefined);setRefresh(v=>v+1);
  }catch(e){setError(formatThrownError(e));}finally{setBusy(false);}}
  return <div className="space-y-4 p-4">
    <h1 className="text-2xl font-semibold">{levels?"Уровни образования":"Виды документов"}</h1>
    <p>{levels?"Пустое значение означает «не указано». «Без образования» — отдельный выбор. Пояснения о классах отображаются только здесь; для документов передаётся выбранное название.":"Виды документов самостоятельны и не объединяются с типами документов. ATTESTATION — Свидетельство; SCHOOL_ATTESTATE — Аттестат."} Коды постоянны. Неактивные значения сохраняются в прежних записях. Использования считаются по явным ссылкам в карточках и документах, без сопоставления свободного текста.</p>
    <div className="flex flex-wrap gap-3"><label>Поиск RU/KK <input className={input} value={query} onChange={e=>setQuery(e.target.value)}/></label><label>Статус <select aria-label="Статус" className={input} value={state} onChange={e=>setState(e.target.value)}><option value="all">Все</option><option value="active">Активные</option><option value="inactive">Неактивные</option></select></label>
      {list.can_manage&&list.schema_ready?<button className={input} onClick={()=>open(null)}>Добавить значение</button>:null}</div>
    {!list.schema_ready?<p role="status">Управление станет доступно после миграции hrlocal309.</p>:null}
    {error?<p role="alert">{error}</p>:null}
    {editing!==undefined?<form className="grid gap-3 rounded border p-3" onSubmit={e=>{e.preventDefault();void save();}}>
      <label>Код <input aria-label="Код" required className={input} disabled={editing!==null||busy} value={form.code} onChange={e=>setForm(v=>({...v,code:e.target.value}))}/></label>
      <label>Название RU <input aria-label="Название RU" required maxLength={500} className={input} disabled={busy} value={form.name_ru} onChange={e=>setForm(v=>({...v,name_ru:e.target.value}))}/></label>
      <label>Название KK <input aria-label="Название KK" required maxLength={500} className={input} disabled={busy} value={form.name_kk} onChange={e=>setForm(v=>({...v,name_kk:e.target.value}))}/></label>
      <label>Порядок <input aria-label="Порядок" type="number" step="1" required className={input} disabled={busy} value={form.sort_order} onChange={e=>setForm(v=>({...v,sort_order:Number(e.target.value)}))}/></label>
      <label><input aria-label="Активно" type="checkbox" disabled={busy} checked={form.is_active} onChange={e=>setForm(v=>({...v,is_active:e.target.checked}))}/> Активно</label>
      {levels?<><label>Пояснение RU <textarea aria-label="Пояснение RU" maxLength={2000} disabled={busy} className={input} value={form.description_ru} onChange={e=>setForm(v=>({...v,description_ru:e.target.value}))}/></label><label>Пояснение KK <textarea aria-label="Пояснение KK" maxLength={2000} disabled={busy} className={input} value={form.description_kk} onChange={e=>setForm(v=>({...v,description_kk:e.target.value}))}/></label></>:null}
      <div className="flex gap-3"><button className={input} disabled={busy}>Сохранить</button><button className={input} type="button" disabled={busy} onClick={()=>setEditing(undefined)}>Отмена</button></div>
    </form>:null}
    <table className="w-full text-left"><thead><tr>{['Код','Название RU','Название KK',...(levels?['Пояснения RU / KK']:[]),'Порядок','Статус','Использований',''].map((h,i)=><th key={i} className="p-2">{h}</th>)}</tr></thead><tbody>{list.items.map(row=><tr key={row.code} className="border-t"><td className="p-2">{row.code}</td><td className="p-2">{row.name_ru}</td><td className="p-2">{row.name_kk}</td>{levels?<td className="p-2">{row.description_ru}<br/>{row.description_kk}</td>:null}<td className="p-2">{row.sort_order}</td><td className="p-2">{row.is_active?'Активно':'Неактивно'}</td><td className="p-2">{row.usage_count??0}</td><td>{list.can_manage&&list.schema_ready?<button className={input} onClick={()=>open(row)}>Редактировать {row.code}</button>:null}</td></tr>)}</tbody></table>
  </div>;
}
