import type {PositionFormValues} from "./PositionForm";
import {formatThrownError} from "@/lib/i18n";

export function positionSaveError(error:unknown):string {
  const e=error as {status?:number;details?:{detail?:unknown}}|null;
  const detail=e?.details?.detail;
  const reasons:Record<string,string>={
    "Unknown position family.":"Выбранный общий вид должности не найден. Выберите его заново из списка.",
    "Confirmed Kazakh title must not be empty.":"Название KK отмечено как подтверждённое, но не заполнено. Заполните его или выберите «Требует уточнения».",
    "Confirmed Kazakh document form must not be empty.":"Документная форма KK отмечена как подтверждённая, но не заполнена. Заполните её или выберите «Требует уточнения».",
    "Position or search synonym already exists.":"Такая должность или поисковый синоним уже существует. Найдите существующую запись перед повторным сохранением.",
    "Search synonym conflicts with another position.":"Поисковый синоним совпадает с другой должностью. Уточните синоним.",
  };
  let message=typeof detail==="string"?reasons[detail]:undefined;
  if(Array.isArray(detail)){
    const labels:Record<string,string>={name:"Название должности",category:"Категория",job_code:"Общий вид должности",name_kk:"Название KK",document_nominative_ru:"Документная форма RU",document_possessive_kk:"Документная форма KK",aliases:"Поисковые синонимы",record_kind:"Тип записи",translation_status:"Статус названия KK",document_form_status:"Статус документной формы KK",expected_revision:"Ревизия записи"};
    const fields=[...new Set(detail.flatMap(issue=>{
      const loc=issue&&typeof issue==="object"?(issue as {loc?:unknown}).loc:null;
      const key=Array.isArray(loc)?String(loc[1]??""):"";
      return labels[key]?[labels[key]]:[];
    }))];
    if(fields.length)message=`Проверьте поля: ${fields.join(", ")}. Сервер отклонил введённые значения.`;
  }
  message??=formatThrownError(error,{fallback:"Не удалось сохранить должность."});
  return e?.status?`${message} (HTTP ${e.status})`:message;
}

export type SavedPosition = PositionFormValues & {position_id?:number;id?:number;revision?:number};
export type PositionSaveResult = {savedValues:PositionFormValues};
export const normalizePositionName=(value:string)=>value.replace(/ -/g,"-").replace(/- /g,"-").trim().replace(/\s+/g," ");

export function positionValues(record: Partial<SavedPosition>): PositionFormValues {
  return {
    name:record.name??"",category:record.category??"other",expected_revision:record.revision??record.expected_revision,
    name_kk:record.name_kk??"",document_nominative_ru:record.document_nominative_ru??record.name??"",
    document_possessive_kk:record.document_possessive_kk??"",translation_status:record.translation_status??"needs_review",
    document_form_status:record.document_form_status??"needs_review",record_kind:record.record_kind??"standalone",
    job_code:record.job_code??"",aliases:record.aliases??[],
  };
}

function aliases(values:string[] = []) {
  const unique=new Map<string,string>();
  for(const value of values){
    const text=value.trim();
    if(text)unique.set(text.normalize("NFKC").toLocaleLowerCase("ru-RU").replace(/[^\p{L}\p{N}]+/gu," ").trim(),text);
  }
  return [...unique.values()].sort();
}

export function positionSignature(values:PositionFormValues):string {
  return JSON.stringify([
    normalizePositionName(values.name),values.category,
    values.name_kk?.trim()??"",values.document_nominative_ru?.trim()||values.name.trim().replace(/\s+/g," "),values.document_possessive_kk?.trim()??"",
    values.translation_status??"needs_review",values.document_form_status??"needs_review",
    values.record_kind??"standalone",values.job_code?.trim()??"",aliases(values.aliases),
  ]);
}

export function verifyPositionSaved(submitted:PositionFormValues,readBack:SavedPosition,id:number):PositionFormValues {
  if(Number(readBack.position_id??readBack.id)!==id)throw new Error("API вернул другую запись должности. Сохранение не подтверждено.");
  if(!Number.isSafeInteger(readBack.revision)||Number(readBack.revision)<1)throw new Error("API не вернул актуальную ревизию должности. Сохранение не подтверждено.");
  const persisted=positionValues(readBack);
  if(positionSignature(submitted)!==positionSignature(persisted))throw new Error("Должность записана, но повторное чтение не подтвердило все поля. Проверьте запись перед повторным сохранением.");
  return persisted;
}
