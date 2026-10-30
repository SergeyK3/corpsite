"use client";
import {personalDataAcknowledgementNames,type PersonalDataAcknowledgementParts} from '../_lib/personalDataAcknowledgement';
export default function PersonalDataAcknowledgementFields({value,onChange,disabled=false,sourceGivenNames}:{value:PersonalDataAcknowledgementParts;onChange:(value:PersonalDataAcknowledgementParts)=>void;disabled?:boolean;sourceGivenNames?:{ru?:string;kk?:string}}){
 const names=personalDataAcknowledgementNames({personal_data:value,source_given_name_ru:sourceGivenNames?.ru,source_given_name_kk:sourceGivenNames?.kk});
 return <fieldset disabled={disabled} className="space-y-2 rounded border p-3" data-testid="personal-data-acknowledgement-fields"><legend>Подпись ознакомления</legend>
 <div className="grid gap-3 sm:grid-cols-2">{(['ru','kk'] as const).flatMap(locale=>([['new_surname','Новая фамилия'],['new_given_name','Новое имя']] as const).map(([part,label])=>{
  const key=`${part}_${locale}` as keyof PersonalDataAcknowledgementParts;const title=`${label} ${locale.toUpperCase()}`;
  return <label key={key} className="block space-y-1"><span>{title}{part==='new_given_name'?' — если имя изменено':''}</span><input aria-label={title} value={value[key]} onChange={e=>onChange({...value,[key]:e.target.value})} className="block w-full rounded border bg-transparent p-2"/></label>;
 }))}</div>
 <p className="text-xs">Новое имя заполняется только при его изменении. Инициал определяется автоматически из прежнего ФИО сотрудника; введённое новое имя имеет приоритет.</p>
 <div className="text-sm" aria-live="polite" data-testid="personal-data-acknowledgement-preview"><p>RU: С приказом ознакомлен: {names.ru||'заполните новую фамилию RU'}</p><p>KK: Бұйрықпен таныстым: {names.kk||'заполните новую фамилию KK'}</p></div>
 </fieldset>;
}
