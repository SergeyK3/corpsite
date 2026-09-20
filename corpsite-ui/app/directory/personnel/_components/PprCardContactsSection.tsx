"use client";
import * as React from "react";
import { getPprPersonContacts, savePprPersonContacts } from "../_lib/pprQueryApi.client";
import { newPprCommandId } from "../_lib/pprCommandApi.client";

export default function PprCardContactsSection({ personId, editable, onSaved }: { personId: number; editable: boolean; onSaved: () => void }) {
  const [item,setItem]=React.useState<Awaited<ReturnType<typeof getPprPersonContacts>>["canonical"]>(null);
  const [fallback,setFallback]=React.useState<Awaited<ReturnType<typeof getPprPersonContacts>>["fallback"]>(null);
  const [form,setForm]=React.useState({mobile_phone:"",email:"",registration_address:"",residence_address:""});
  const [editing,setEditing]=React.useState(false); const [busy,setBusy]=React.useState(false); const [error,setError]=React.useState<string|null>(null);
  const load=React.useCallback(async()=>{const value=await getPprPersonContacts(personId);setItem(value.canonical);setFallback(value.fallback); const c=value.canonical??value.fallback;setForm({mobile_phone:c?.mobile_phone??"",email:c?.email??"",registration_address:c?.registration_address??"",residence_address:c?.residence_address??""});},[personId]);
  React.useEffect(()=>{void load().catch(()=>setError("Не удалось загрузить контакты."));},[load]);
  React.useEffect(()=>{const warn=(event:BeforeUnloadEvent)=>{if(editing){event.preventDefault();event.returnValue="";}};window.addEventListener("beforeunload",warn);return()=>window.removeEventListener("beforeunload",warn);},[editing]);
  const field=(key:keyof typeof form,label:string)=><label className="block text-sm"><span className="text-zinc-500">{label}</span><input disabled={!editing||busy} value={form[key]} onChange={e=>setForm(v=>({...v,[key]:e.target.value}))} className="mt-1 w-full rounded border p-2 disabled:bg-zinc-100" /></label>;
  async function save(){setBusy(true);setError(null);try{await savePprPersonContacts(personId,{command_id:newPprCommandId(),expected_version:item?.version??null,...form});await load();setEditing(false);onSaved();}catch(e){setError(e instanceof Error?e.message:"Не удалось сохранить контакты.");}finally{setBusy(false);}}
  return <div className="space-y-3" data-testid="ppr-card-contacts">{!item&&fallback?<p className="text-xs text-amber-700">Показаны неподтверждённые контакты из прежнего контура; они станут каноническими только после сохранения.</p>:null}<div className="grid gap-3 sm:grid-cols-2">{field("mobile_phone","Мобильный телефон")}{field("email","Email")}{field("registration_address","Адрес регистрации")}{field("residence_address","Адрес проживания")}</div>{error?<p className="text-sm text-red-600">{error}</p>:null}{editable&&!editing?<button type="button" className="rounded border px-3 py-1.5 text-sm" onClick={()=>setEditing(true)}>Редактировать</button>:null}{editing?<div className="flex gap-2"><button type="button" className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white" disabled={busy} onClick={()=>void save()}>Сохранить</button><button type="button" className="rounded border px-3 py-1.5 text-sm" disabled={busy} onClick={()=>{void load();setEditing(false);}}>Отмена</button></div>:null}</div>;
}
