"use client";
import * as React from "react";
import { createPortal } from "react-dom";
import type { DocumentPosition } from "../_lib/personnelOrderPositions";

export default function PersonnelOrderPositionPicker({label,value,positions,loading,error,onSelect,onCustomChange}: {
  label:string; value:string; positions:DocumentPosition[]; loading:boolean; error:boolean;
  onSelect:(position:DocumentPosition)=>void; onCustomChange?:(value:string)=>void;
}) {
  const [open,setOpen]=React.useState(false),[query,setQuery]=React.useState("");
  const root=React.useRef<HTMLDivElement>(null),popup=React.useRef<HTMLDivElement>(null),input=React.useRef<HTMLInputElement>(null);
  const [placement,setPlacement]=React.useState({left:0,top:0,width:0});
  const listId=React.useId();
  React.useEffect(()=>{
    const close=(event:MouseEvent)=>{if(!root.current?.contains(event.target as Node)&&!popup.current?.contains(event.target as Node))setOpen(false);};
    document.addEventListener("mousedown",close);return()=>document.removeEventListener("mousedown",close);
  },[]);
  const show=()=>{setQuery("");setOpen(true);};
  const filtered=positions.filter(p=>!query || `${p.name} ${p.name_kk||""} ${(p as DocumentPosition & {aliases?:string[]}).aliases?.join(" ")||""}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  React.useLayoutEffect(()=>{
    if(!open)return;
    const update=()=>{const rect=root.current?.getBoundingClientRect();if(!rect)return;const height=Math.min(330,Math.max(120,filtered.length*40+70));setPlacement({left:rect.left,width:rect.width,top:window.innerHeight-rect.bottom<height&&rect.top>height?rect.top-height-4:rect.bottom+4});};
    update();window.addEventListener("resize",update);window.addEventListener("scroll",update,true);
    return()=>{window.removeEventListener("resize",update);window.removeEventListener("scroll",update,true);};
  },[open,filtered.length]);
  return <div ref={root} className="relative">
    <div className="flex gap-1">
      <input ref={input} aria-label={label} role="combobox" aria-expanded={open} aria-controls={listId} aria-haspopup="listbox" value={value} readOnly={!onCustomChange} onChange={e=>onCustomChange?.(e.target.value)} onClick={show} onKeyDown={e=>{
        if(e.key==="Escape"){setOpen(false);e.stopPropagation();}
        if(e.key==="ArrowDown"){e.preventDefault();show();requestAnimationFrame(()=>popup.current?.querySelector<HTMLButtonElement>('[role="option"]')?.focus());}
      }} className="mt-1 w-full rounded border border-zinc-300 bg-white p-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"/>
      <button type="button" aria-label={`Выбрать: ${label}`} aria-expanded={open} onClick={()=>open?setOpen(false):show()} className="mt-1 rounded border px-3">▾</button>
    </div>
    {open ? createPortal(<div ref={popup} style={placement} className="fixed z-[90] rounded border border-zinc-300 bg-white p-2 shadow-xl dark:border-zinc-700 dark:bg-zinc-950">
      <input aria-label={`Поиск: ${label}`} value={query} onChange={e=>setQuery(e.target.value)} placeholder="Поиск по названиям RU / KK" className="mb-2 w-full rounded border p-2 text-sm"/>
      {loading?<p role="status">Загрузка должностей…</p>:null}
      {error?<p role="status">Не удалось загрузить справочник должностей.</p>:null}
      <div id={listId} role="listbox" aria-label="Должности" className="max-h-64 overflow-auto">
        {filtered.map(p=><button key={p.id} type="button" role="option" aria-selected={value===p.name} onClick={()=>{onSelect(p);setOpen(false);input.current?.focus();}} onKeyDown={e=>{
          if(e.key==="Escape"){setOpen(false);input.current?.focus();e.stopPropagation();}
          if(e.key==="ArrowDown"||e.key==="ArrowUp"){e.preventDefault();const sibling=e.key==="ArrowDown"?e.currentTarget.nextElementSibling:e.currentTarget.previousElementSibling;(sibling as HTMLElement|null)?.focus();}
        }} className="block w-full rounded px-3 py-2 text-left text-sm hover:bg-blue-50 focus:bg-blue-50 dark:hover:bg-zinc-800 dark:focus:bg-zinc-800">{p.name}</button>)}
        {!loading&&!error&&!filtered.length?<p className="p-2 text-sm">Должности не найдены.</p>:null}
      </div>
    </div>,document.body):null}
  </div>;
}
