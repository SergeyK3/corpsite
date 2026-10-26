"use client";

import * as React from "react";
import ExportExcelButton from "@/components/ExportExcelButton";
import {apiFetchJson} from "@/lib/api";
import {formatThrownError} from "@/lib/i18n";
import {allExportPages, type ExcelTable} from "@/lib/tableExport";

export type MedicalSpecialty = {medical_specialty_id:number; name:string; name_kk:string|null; group_id:number; group_name:string; is_active:boolean};
type Group = {group_id:number; name:string};
type List = {items:MedicalSpecialty[]; total:number};
const API="/directory/medical-specialties";
const PAGE_SIZE=20;
const input="rounded-lg border border-zinc-200 bg-transparent px-3 py-2 dark:border-zinc-700";

export default function MedicalSpecialtiesPage(){
  const [search,setSearch]=React.useState("");
  const [group,setGroup]=React.useState("");
  const [active,setActive]=React.useState("active");
  const [page,setPage]=React.useState(0);
  const [groups,setGroups]=React.useState<Group[]>([]);
  const [data,setData]=React.useState<List>({items:[],total:0});
  const [loading,setLoading]=React.useState(true);
  const [error,setError]=React.useState("");
  const [groupError,setGroupError]=React.useState("");
  React.useEffect(()=>{let live=true;
    apiFetchJson<{items:Group[]}>("/directory/medical-specialty-groups").then(r=>{if(live)setGroups(r.items);}).catch(e=>{if(live)setGroupError(formatThrownError(e));});
    return()=>{live=false;};
  },[]);
  React.useEffect(()=>{let live=true;setLoading(true);setError("");
    apiFetchJson<List>(API,{query:{q:search||undefined,group_id:group||undefined,is_active:active==="active",limit:PAGE_SIZE,offset:page*PAGE_SIZE}})
      .then(r=>{if(live)setData(r);}).catch(e=>{if(live){setError(formatThrownError(e));setData({items:[],total:0});}}).finally(()=>{if(live)setLoading(false);});
    return()=>{live=false;};
  },[search,group,active,page]);
  async function loadExcel():Promise<ExcelTable>{
    // Capture all visible filters once; export starts at zero, not the UI page.
    const filters={q:search||undefined,group_id:group||undefined,is_active:active==="active"};
    const rows=await allExportPages<MedicalSpecialty>(pagination=>apiFetchJson<List>(API,{query:{...filters,...pagination}}),PAGE_SIZE);
    return {headers:["ID","На русском языке","Қазақша атауы","Группа","Активна"],rows:rows.map(r=>[r.medical_specialty_id,r.name,r.name_kk,r.group_name,r.is_active])};
  }
  return <div className="space-y-4 p-4 text-zinc-900 dark:text-zinc-50">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl font-semibold">Медицинские специальности</h1>
      <ExportExcelButton load={loadExcel} filename="Медицинские_специальности.xlsx" disabled={loading||!!error}/>
    </div>
    <div className="flex flex-wrap gap-3">
      <label className="flex flex-col gap-1 text-sm">Поиск по RU / KK<input className={input} value={search} placeholder="Русское или казахское название" onChange={e=>{setSearch(e.target.value);setPage(0);}}/></label>
      <label className="flex flex-col gap-1 text-sm">Группа<select className={input} value={group} onChange={e=>{setGroup(e.target.value);setPage(0);}}><option value="">Все группы</option>{groups.map(g=><option key={g.group_id} value={g.group_id}>{g.name}</option>)}</select></label>
      <label className="flex flex-col gap-1 text-sm">Статус<select className={input} value={active} onChange={e=>{setActive(e.target.value);setPage(0);}}><option value="active">Активные</option><option value="all">Все</option></select></label>
    </div>
    {error&&<p role="alert">{error}</p>}{groupError&&<p role="alert">{groupError}</p>}
    <p role="status">{loading?"Загрузка…":`Всего: ${data.total}`}</p>
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-700">
      <table className="w-full text-left text-sm"><thead className="bg-zinc-100 dark:bg-zinc-900"><tr>{["ID","На русском языке","Қазақша атауы","Группа","Статус"].map(h=><th key={h} className="px-3 py-2">{h}</th>)}</tr></thead>
      <tbody>{data.items.map(r=><tr key={r.medical_specialty_id} className="border-t border-zinc-200 dark:border-zinc-700"><td className="px-3 py-2">{r.medical_specialty_id}</td><td className="px-3 py-2">{r.name}</td><td className="px-3 py-2">{r.name_kk||"—"}</td><td className="px-3 py-2">{r.group_name}</td><td className="px-3 py-2">{r.is_active?"Активна":"Неактивна"}</td></tr>)}</tbody></table>
      {!loading&&!data.items.length&&!error&&<p className="p-3">Специальности не найдены.</p>}
    </div>
    <div className="flex items-center gap-3"><button className={input} disabled={loading||page===0} onClick={()=>setPage(p=>p-1)}>Назад</button><span>Страница {page+1} из {Math.max(1,Math.ceil(data.total/PAGE_SIZE))}</span><button className={input} disabled={loading||(page+1)*PAGE_SIZE>=data.total} onClick={()=>setPage(p=>p+1)}>Далее</button></div>
  </div>;
}
