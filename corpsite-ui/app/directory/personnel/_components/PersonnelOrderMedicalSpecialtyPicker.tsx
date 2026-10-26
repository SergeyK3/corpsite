"use client";
import * as React from "react";
import {apiFetchJson} from "@/lib/api";

export type MedicalSpecialtySnapshot={medical_specialty_id:number;name_ru:string;name_kk:string};
type Row={medical_specialty_id:number;name:string;name_kk:string|null;is_active:boolean};
export default function PersonnelOrderMedicalSpecialtyPicker({value,onChange,disabled=false}:{value?:MedicalSpecialtySnapshot|null;onChange:(value:MedicalSpecialtySnapshot|null)=>void;disabled?:boolean}){
 const [rows,setRows]=React.useState<Row[]>([]),[query,setQuery]=React.useState(""),[loading,setLoading]=React.useState(true),[error,setError]=React.useState(""),[retry,setRetry]=React.useState(0);
 const [open,setOpen]=React.useState(false),[editing,setEditing]=React.useState(false);
 const id=React.useId();
 React.useEffect(()=>{setQuery('');setEditing(false);setOpen(false);},[value?.medical_specialty_id,value?.name_ru,value?.name_kk]);
 React.useEffect(()=>{let live=true;setLoading(true);setError("");
  (async()=>{const result:Row[]=[];let offset=0;
   while(true){const page=await apiFetchJson<{items:Row[];total:number}>("/directory/medical-specialties",{query:{is_active:true,limit:1000,offset}});result.push(...page.items);offset+=page.items.length;if(!page.items.length||offset>=page.total)break;}
   if(live)setRows(result.filter(r=>r.is_active));
  })().catch(()=>{if(live)setError("Не удалось загрузить медицинские специальности. Можно повторить загрузку или оставить поле пустым.");}).finally(()=>{if(live)setLoading(false);});return()=>{live=false;};
 },[retry]);
 const found=rows.filter(r=>`${r.name} ${r.name_kk||""}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
 const selectedText=value?[value.name_ru,value.name_kk].filter(Boolean).join(' / '):'';
 const select=(row:Row)=>{if(!row.name_kk)return;onChange({medical_specialty_id:row.medical_specialty_id,name_ru:row.name,name_kk:row.name_kk});setQuery('');setEditing(false);setOpen(false);};
 const close=()=>{setOpen(false);setEditing(false);setQuery('');};
 const listVisible=open&&!loading&&!error;
 return <div className="space-y-2 rounded border p-3" data-testid="order-medical-specialty">
  <label htmlFor={id} className="block text-sm font-medium">Медицинская специальность (необязательно)</label>
  <div className="flex items-center gap-2"><input id={id} role="combobox" aria-autocomplete="list" aria-expanded={Boolean(listVisible)} aria-controls={listVisible?`${id}-options`:undefined} value={editing?query:selectedText} disabled={disabled} placeholder="Поиск по RU или KK" autoComplete="off"
   onFocus={event=>{setQuery('');setEditing(false);setOpen(true);event.currentTarget.select();}} onBlur={close}
   onChange={e=>{setQuery(e.target.value);setEditing(true);setOpen(true);}}
   onKeyDown={e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close();}if(e.key==='ArrowDown'){e.preventDefault();setOpen(true);}if(e.key==='Enter'&&listVisible){e.preventDefault();const row=found.find(row=>row.name_kk);if(row)select(row);}}}
   className="min-w-0 flex-1 rounded border bg-transparent px-3 py-2"/>
  {value&&<button type="button" disabled={disabled} onClick={()=>{onChange(null);close();}} className="shrink-0 rounded border px-2 py-1 text-sm">Очистить специальность</button>}</div>
  <p className="text-xs">Специальность сохраняется только в пункте приказа. Без выбора текст формируется без скобок.</p>
  {loading&&<p role="status">Загружаются специальности…</p>}
  {error&&<p role="alert">{error} <button type="button" disabled={disabled} onClick={()=>setRetry(n=>n+1)}>Повторить загрузку</button></p>}
  {listVisible&&<div id={`${id}-options`} role="listbox" aria-label="Медицинские специальности" className="max-h-48 overflow-y-auto rounded border">{found.map(r=><button type="button" role="option" aria-selected={r.medical_specialty_id===value?.medical_specialty_id} key={r.medical_specialty_id} disabled={disabled||!r.name_kk} onMouseDown={e=>e.preventDefault()} onClick={()=>select(r)} className="block w-full px-3 py-2 text-left hover:bg-zinc-100 dark:hover:bg-zinc-800">{r.name} / {r.name_kk||"нет названия KK"}</button>)}{!found.length&&<p className="p-2">Совпадений нет.</p>}</div>}
 </div>;
}
