"use client";
import {useEffect,useState} from "react";
import {apiFetchJson} from "@/lib/api";
import {formatThrownError} from "@/lib/i18n";
import {useCurrentUser} from "@/lib/currentUser";
import {EDUCATION_PROGRAM_KINDS_API as API,type EducationProgramKind,type EducationProgramKindList} from "../personnel/_lib/educationProgramKinds";

const blank={code:"",name_ru:"",name_kk:"",sort_order:0,is_active:true};
const input="rounded border bg-transparent p-2";
export default function EducationProgramKindsPage(){
  const standaloneUser=useCurrentUser();
  const documentationViewer=standaloneUser?.is_documentation_viewer===true || standaloneUser?.is_sysadmin_assistant===true;
  const [list,setList]=useState<EducationProgramKindList & {can_manage?:boolean}>({items:[],total:0,schema_ready:false});
  const [query,setQuery]=useState("");const [state,setState]=useState("all");const [refresh,setRefresh]=useState(0);
  const [editing,setEditing]=useState<EducationProgramKind|null|undefined>(undefined);const [form,setForm]=useState(blank);
  const [error,setError]=useState("");const [busy,setBusy]=useState(false);
  useEffect(()=>{let live=true;void apiFetchJson<typeof list>(API,{query:{q:query,state}}).then(r=>{if(live){setList(r);setError("");}}).catch(e=>{if(live)setError(formatThrownError(e));});return()=>{live=false;};},[query,state,refresh]);
  function open(row:EducationProgramKind|null){setEditing(row);setForm(row?{code:row.code,name_ru:row.name_ru,name_kk:row.name_kk,sort_order:row.sort_order,is_active:row.is_active}:blank);setError("");}
  async function save(){setBusy(true);setError("");try{
    const {code,...values}=form;
    await apiFetchJson(API+(editing?'/'+encodeURIComponent(editing.code):''),{method:editing?'PATCH':'POST',body:editing?{...values,expected_revision:editing.revision}:form});
    setEditing(undefined);setRefresh(v=>v+1);
  }catch(e){setError(formatThrownError(e));}finally{setBusy(false);}}
  return <div className="space-y-4 p-4">
    <h1 className="text-2xl font-semibold">Виды программ и подготовки</h1>
    <p>Коды используются в личных карточках и не переименовываются. Неактивные значения сохраняются в прежних записях; для новых записей они недоступны.</p>
    <div className="flex flex-wrap gap-3"><label>Поиск RU/KK <input className={input} value={query} onChange={e=>setQuery(e.target.value)}/></label><label>Статус <select className={input} value={state} onChange={e=>setState(e.target.value)}><option value="all">Все</option><option value="active">Активные</option><option value="inactive">Неактивные</option></select></label>
      {(list.can_manage||documentationViewer)&&list.schema_ready?<button className={input} onClick={()=>open(null)}>Добавить значение</button>:null}</div>
    {!list.schema_ready?<p role="status">Управление станет доступно после миграции hrlocal308.</p>:null}
    {error?<p role="alert">{error}</p>:null}
    {editing!==undefined?<form className="grid gap-3 rounded border p-3" onSubmit={e=>{e.preventDefault();void save();}}>
      <label>Код <input aria-label="Код" required className={input} disabled={editing!==null||busy} value={form.code} onChange={e=>setForm(v=>({...v,code:e.target.value}))}/></label>
      <label>Название RU <input aria-label="Название RU" required maxLength={500} className={input} disabled={busy} value={form.name_ru} onChange={e=>setForm(v=>({...v,name_ru:e.target.value}))}/></label>
      <label>Название KK <input aria-label="Название KK" required maxLength={500} className={input} disabled={busy} value={form.name_kk} onChange={e=>setForm(v=>({...v,name_kk:e.target.value}))}/></label>
      <label>Порядок <input aria-label="Порядок" type="number" step="1" required className={input} disabled={busy} value={form.sort_order} onChange={e=>setForm(v=>({...v,sort_order:Number(e.target.value)}))}/></label>
      <label><input aria-label="Активно" type="checkbox" disabled={busy} checked={form.is_active} onChange={e=>setForm(v=>({...v,is_active:e.target.checked}))}/> Активно</label>
      <div className="flex gap-3"><button className={input} disabled={busy}>Сохранить</button><button className={input} type="button" disabled={busy} onClick={()=>setEditing(undefined)}>Отмена</button></div>
    </form>:null}
    <table className="w-full text-left"><thead><tr>{['Код','Название RU','Название KK','Статус','Записей карточек',''].map((h,i)=><th key={i} className="p-2">{h}</th>)}</tr></thead><tbody>{list.items.map(row=><tr key={row.code} className="border-t"><td className="p-2">{row.code}</td><td className="p-2">{row.name_ru}</td><td className="p-2">{row.name_kk}</td><td className="p-2">{row.is_active?'Активно':'Неактивно'}</td><td className="p-2">{row.usage_count??0}</td><td>{(list.can_manage||documentationViewer)&&list.schema_ready?<button className={input} onClick={()=>open(row)}>Редактировать {row.code}</button>:null}</td></tr>)}</tbody></table>
  </div>;
}
