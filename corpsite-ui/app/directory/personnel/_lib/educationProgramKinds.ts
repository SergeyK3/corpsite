"use client";
import { useEffect, useState } from "react";
import { apiFetchJson } from "@/lib/api";

export const EDUCATION_PROGRAM_KINDS_API = "/api/ppr/education-program-kinds";
export type EducationProgramKind = { code:string; name_ru:string; name_kk:string; is_active:boolean; sort_order:number; revision:number; usage_count?:number };
export type EducationProgramKindList = { items:EducationProgramKind[]; total:number; schema_ready:boolean };

export function useEducationProgramKinds(enabled=true) {
  const [items,setItems]=useState<EducationProgramKind[]>([]);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(enabled);
  useEffect(()=>{
    if(!enabled){setLoading(false);return;}
    let active=true;
    setLoading(true);
    void apiFetchJson<EducationProgramKindList>(EDUCATION_PROGRAM_KINDS_API).then(r=>{if(active){setItems(r.items);setError("");}})
      .catch(()=>{if(active)setError("Не удалось загрузить виды программ и подготовки. Обновите страницу.");})
      .finally(()=>{if(active)setLoading(false);});
    return()=>{active=false;};
  },[enabled]);
  return {items,error,loading};
}

export function programKindOptions(items:EducationProgramKind[], currentCode?:string, currentLabel?:string) {
  const options=items.filter(row=>row.is_active||row.code===currentCode).map(row=>({value:row.code,label:row.name_ru+(!row.is_active?" (неактивно)":"")}));
  if(currentCode&&!options.some(row=>row.value===currentCode))options.push({value:currentCode,label:currentLabel||currentCode});
  return options;
}
