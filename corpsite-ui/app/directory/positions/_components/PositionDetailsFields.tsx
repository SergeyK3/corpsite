"use client";
import * as React from "react";
import {apiFetchJson} from "@/lib/api";

export type PositionDetails = {
  name_kk?:string; document_nominative_ru?:string; document_possessive_kk?:string;
  translation_status?:"confirmed"|"needs_review"; document_form_status?:"confirmed"|"needs_review";
  record_kind?:"standalone"|"variant"|"search_synonym";job_code?:string;aliases?:string[];expected_revision?:number;
};
type Family={job_code:string;job_nameru:string;job_namekk:string;job_namekk_doc:string};
export default function PositionDetailsFields({value,onChange}:{value:PositionDetails;onChange:(v:Partial<PositionDetails>)=>void}){
  const [families,setFamilies]=React.useState<Family[]>([]);
  const [family,setFamily]=React.useState<Family|null>(null);
  const [error,setError]=React.useState("");const [busy,setBusy]=React.useState(false);
  React.useEffect(()=>{let live=true;apiFetchJson<{items:Family[]}>("/directory/position-families").then(r=>{if(live)setFamilies(r.items)}).catch(()=>{if(live)setError("Не удалось загрузить общие виды должностей")});return()=>{live=false}},[]);
  async function saveFamily(){
    if(!family||busy)return;setBusy(true);setError("");
    try{const exists=families.some(f=>f.job_code===family.job_code);const {job_code,...body}=family;
      await apiFetchJson(exists?`/directory/position-families/${encodeURIComponent(job_code)}`:`/directory/position-families?code=${encodeURIComponent(job_code)}`,{method:exists?"PUT":"POST",body});
      setFamilies(fs=>[...fs.filter(f=>f.job_code!==job_code),family]);onChange({job_code});setFamily(null);
    }catch{setError("Не удалось сохранить общий вид. Проверьте код, названия RU/KK и документную форму.")}finally{setBusy(false)}
  }
  const input="mt-1 block w-full rounded border bg-transparent p-2";
  return <fieldset className="space-y-3 rounded border p-3">
    <legend>Названия и общий вид</legend>
    <p className="text-sm">Точное название относится к этой записи. Общий вид группирует варианты; номера отделений и ID сохраняются.</p>
    <label className="block text-sm">Общий вид должности<select className={input} value={value.job_code||""} disabled={busy} onChange={e=>{setFamily(null);setError("");onChange({job_code:e.target.value});}}><option value="">Без связи / требует уточнения</option>{families.map(f=><option key={f.job_code} value={f.job_code}>{f.job_nameru} ({f.job_code})</option>)}</select></label>
    <label className="block text-sm">Тип записи<select className={input} value={value.record_kind||"standalone"} onChange={e=>onChange({record_kind:e.target.value as PositionDetails['record_kind']})}><option value="standalone">Отдельная должность</option><option value="variant">Вариант названия общей должности</option><option value="search_synonym">Историческое название / поисковый синоним</option></select></label>
    {([['name_kk','Название KK'],['document_nominative_ru','Документная форма RU'],['document_possessive_kk','Документная форма KK']] as const).map(([key,label])=><label key={key} className="block text-sm">{label}<input className={input} maxLength={500} value={value[key]||""} onChange={e=>onChange({[key]:e.target.value})} /></label>)}
    {([['translation_status','Статус названия KK'],['document_form_status','Статус документной формы KK']] as const).map(([key,label])=><label key={key} className="block text-sm">{label}<select className={input} value={value[key]||"needs_review"} onChange={e=>onChange({[key]:e.target.value})}><option value="needs_review">Требует уточнения</option><option value="confirmed">Подтверждено</option></select></label>)}
    <label className="block text-sm">Поисковые синонимы (по одному в строке)<textarea className={input} value={(value.aliases||[]).join('\n')} onChange={e=>onChange({aliases:e.target.value.split('\n')})} /></label>
    <details><summary>Настройки общего вида</summary>
      <button type="button" className="rounded border p-2" onClick={()=>setFamily(families.find(f=>f.job_code===value.job_code)||{job_code:"",job_nameru:"",job_namekk:"",job_namekk_doc:""})}>Редактировать или добавить общий вид</button>
      {family&&<div className="space-y-2 p-2"><p className="text-sm">Изменяется группа {family.job_code||"(новая)"}. Точные названия вариантов и сохранённые приказы остаются прежними.</p>{(['job_code','job_nameru','job_namekk','job_namekk_doc'] as const).map((key,i)=><label key={key} className="block text-sm">{['Код общего вида','Общее название RU','Общее название KK','Общая документная форма KK'][i]}<input className={input} maxLength={500} value={family[key]} disabled={key==='job_code'&&families.some(f=>f.job_code===family.job_code)} onChange={e=>setFamily(f=>f?{...f,[key]:e.target.value}:f)} /></label>)}<button disabled={busy} type="button" className="rounded border p-2" onClick={()=>void saveFamily()}>Сохранить общий вид</button> <button type="button" onClick={()=>setFamily(null)}>Закрыть настройки</button></div>}
    </details>
    {error&&<p role="alert" className="text-sm text-red-700">{error}</p>}
  </fieldset>;
}
