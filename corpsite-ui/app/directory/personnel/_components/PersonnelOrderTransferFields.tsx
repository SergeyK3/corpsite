"use client";

import * as React from "react";
import { getPositions } from "@/app/directory/employees/_lib/api.client";
import {apiFetchJson} from "@/lib/api";
import {applyTransferPosition,type TransferPositionRecord,type TransferPositionSnapshot} from "../_lib/personnelOrderTransferPosition";
import type { OrgUnitSelectOption } from "@/lib/orgUnitsSelect";
import {russianReferenceCase} from '../_lib/personnelOrderRussianWording';
import {refreshAutomaticForm} from '../_lib/personnelOrderConcurrentForms';
import {concurrentDepartmentErrors,concurrentDepartmentGenitive,departmentLooksLikePerson, type ConcurrentDepartmentSource} from '../_lib/personnelOrderConcurrentDepartment';
import {calculateKazakhOrgUnitGenitive,calculateKazakhPositionPossessive} from '../_lib/kazakhDocumentForms';
import { generatePersonnelOrderBasisText } from "../_lib/personnelOrderBasisGenerate";
import { normalizePersonnelOrderBasisText } from "../_lib/personnelOrderBasisText";
import type { PersonnelOrderBasisType } from "../_lib/personnelOrderEditorialTypes";
import {selectSecondBasis,editSecondBasis} from '../_lib/personnelOrderSecondBasis';

export type TransferFields = {
  position_ru: string; position_kk: string; org_unit_ru: string; org_unit_kk: string;
  rate: string; basis_ru: string; basis_kk: string;
  position_genitive_ru?: string; org_unit_genitive_ru?: string; total_rate?: string; remaining_rate?: string; assignment_id?: number;
  position_id?: number; org_unit_id?: number; basis_type?: PersonnelOrderBasisType;
  basis_second_ru?: string; basis_second_kk?: string;
  basis_type_ru?: string; basis_type_kk?: string;
  basis_second_type_ru?: string; basis_second_type_kk?: string;
  basis_second_overrides?:{ru?:boolean;kk?:boolean};
  basis_detail_ru?:string; basis_detail_kk?:string;
  basis_second_detail_ru?:string; basis_second_detail_kk?:string;
  position_dictionary?: TransferPositionSnapshot;
  position_overrides?: {ru?:boolean;kk?:boolean};
};
type Option = { id: string; ru: string; kk: string; documentKK?: string; searchText?: string; needsReview?:boolean };
const inputClass = "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900";
const basisTypes: PersonnelOrderBasisType[] = ["PERSONAL_APPLICATION", "MEMO", "MANAGEMENT_SUBMISSION", "MEDICAL_CONCLUSION", "COMMISSION_PROTOCOL", "COURT_ACT"];
const basisOptions: Option[] = basisTypes.map(id => ({
  id,
  ru: normalizePersonnelOrderBasisText(generatePersonnelOrderBasisText({ basisType: id, subjectEmployeeId: null, subjectEmployeeName: null }, "ru"), "ru"),
  kk: normalizePersonnelOrderBasisText(generatePersonnelOrderBasisText({ basisType: id, subjectEmployeeId: null, subjectEmployeeName: null }, "kk"), "kk"),
}));

function SearchField({ label, value, options, locale, onEdit, onSelect, disabled }: {
  label: string; value: string; options: Option[]; locale: "ru" | "kk";
  onEdit: (value: string) => void; onSelect: (option: Option, previousText: string) => void; disabled?: boolean;
}) {
  const id = React.useId();
  const [open, setOpen] = React.useState(false);
  const [searching, setSearching] = React.useState(false);
  const previousText = React.useRef(value);
  const [active, setActive] = React.useState(0);
  const query = searching ? value.toLocaleLowerCase().trim() : "";
  const filtered = options.filter(o => `${o.ru} ${o.kk} ${o.id} ${o.searchText || ""}`.toLocaleLowerCase().includes(query));
  function select(option: Option) { onSelect(option, previousText.current); setOpen(false); setSearching(false); }
  return <div className="relative">
    <label htmlFor={id} className="block text-sm font-medium">{label}</label>
    <div className="relative">
      <input id={id} aria-label={label} role="combobox" aria-autocomplete="list" aria-expanded={open} aria-controls={open ? `${id}-list` : undefined} aria-activedescendant={open && filtered[active] ? `${id}-option-${active}` : undefined} autoComplete="off" value={value} disabled={disabled} className={`${inputClass} pr-10`}
        onFocus={() => { previousText.current = value; setOpen(true); setSearching(false); setActive(0); }}
        onChange={e => { if (!searching) previousText.current = value; onEdit(e.target.value); setOpen(true); setSearching(true); setActive(0); }}
        onBlur={() => setOpen(false)}
        onKeyDown={e => {
          if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setOpen(false); }
          if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); setOpen(true); setActive(i => Math.max(0, Math.min(filtered.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))); }
          if (e.key === "Enter" && open) { e.preventDefault(); if (filtered[active]) select(filtered[active]); else setOpen(false); }
        }} />
      <button type="button" aria-label={`Открыть список: ${label}`} disabled={disabled} className="absolute right-2 top-3 px-1 text-xs" onMouseDown={e => e.preventDefault()} onClick={() => { previousText.current = value; setOpen(v => !v); setSearching(false); setActive(0); }}>▾</button>
    </div>
    {open ? <div role="listbox" id={`${id}-list`} aria-label={`Варианты: ${label}`} className="absolute z-30 max-h-52 w-full overflow-y-auto rounded border border-zinc-300 bg-white shadow-lg dark:border-zinc-700 dark:bg-zinc-900">
      {filtered.map((option, index) => <button key={option.id} id={`${id}-option-${index}`} type="button" role="option" aria-selected={index === active} data-record-id={option.id} className="block w-full px-3 py-2 text-left text-sm hover:bg-blue-50 dark:hover:bg-zinc-800" onMouseDown={e => e.preventDefault()} onClick={() => select(option)}>
        {option[locale] || `Перевод ${locale.toUpperCase()} отсутствует — ${option.ru || option.kk}`}<span className="ml-2 text-xs text-zinc-500">#{option.id}</span>{option.searchText && option.searchText !== option.ru ? <span className="block text-xs text-zinc-500">{option.searchText}</span> : null}
      </button>)}
      {!filtered.length ? <p className="px-3 py-2 text-xs text-zinc-500">Совпадений нет. Введённый текст сохранён как ручное значение.</p> : null}
    </div> : null}
  </div>;
}

export type BasisFieldsValue = Pick<TransferFields, 'basis_ru' | 'basis_kk' | 'basis_second_ru' | 'basis_second_kk' | 'basis_type_ru' | 'basis_type_kk' | 'basis_second_type_ru' | 'basis_second_type_kk' | 'basis_second_overrides' | 'basis_detail_ru' | 'basis_detail_kk' | 'basis_second_detail_ru' | 'basis_second_detail_kk'>;

export function PersonnelOrderBasisFields({value,onChange,disabled=false,firstLabel='Первое основание',onFirstSelect}: {
  value:BasisFieldsValue; onChange:(change:Partial<BasisFieldsValue>)=>void; disabled?:boolean;
  firstLabel?:string; onFirstSelect?:(option:Option,locale:'ru'|'kk',previousText:string)=>void;
}) {
  const hasSecond=Boolean(value.basis_second_ru || value.basis_second_kk || value.basis_second_detail_ru || value.basis_second_detail_kk);
  const [secondVisible,setSecondVisible]=React.useState(hasSecond);
  React.useEffect(()=>{if(hasSecond)setSecondVisible(true);},[hasSecond]);
  function clarification(second:boolean,locale:'ru'|'kk'){
    const key=second?`basis_second_detail_${locale}` as const:`basis_detail_${locale}` as const;
    const label=`Уточнение ${second?'второго':'первого'} основания (${locale.toUpperCase()})`;
    return <label className="mt-2 block text-sm">{label}<textarea aria-label={label} maxLength={2000} disabled={disabled} value={value[key] || ''} onChange={event=>onChange({[key]:event.target.value})} className={inputClass} placeholder="Необязательно"/></label>;
  }
  return <div className="space-y-3" data-testid="personnel-order-basis-choices">
    <p className="text-xs text-zinc-500">Уточнение дописывается после выбранной фразы. RU и KK заполняются отдельно.</p>
    <div className="grid gap-3 sm:grid-cols-2">{(['ru','kk'] as const).map(locale=><div key={locale}><SearchField label={`${firstLabel} (${locale.toUpperCase()})`} value={value[`basis_${locale}`]} locale={locale} options={basisOptions} disabled={disabled}
      onEdit={text=>onChange({[`basis_${locale}`]:text})} onSelect={(option,previousText)=>{
        if(onFirstSelect)onFirstSelect(option,locale,previousText);
        else onChange({[`basis_${locale}`]:option[locale]});
        onChange({[`basis_type_${locale}`]:option.id});
      }}/>{clarification(false,locale)}</div>)}</div>
    {secondVisible ? <div className="space-y-2 rounded border p-3" data-testid="personnel-order-second-basis">
      <div className="grid gap-3 sm:grid-cols-2">{(['ru','kk'] as const).map(locale=><div key={locale}><SearchField label={`Второе основание (${locale.toUpperCase()})`} value={value[`basis_second_${locale}`] || ''} locale={locale} options={basisOptions} disabled={disabled}
        onEdit={text=>onChange(editSecondBasis(value,locale,text))} onSelect={option=>onChange(selectSecondBasis(value,option,locale,basisOptions))}/>{clarification(true,locale)}</div>)}</div>
      <button type="button" disabled={disabled} className="text-sm text-red-700" onClick={()=>{onChange({basis_second_ru:'',basis_second_kk:'',basis_second_type_ru:'',basis_second_type_kk:'',basis_second_overrides:{},basis_second_detail_ru:'',basis_second_detail_kk:''});setSecondVisible(false);}}>Удалить основание</button>
    </div> : <button type="button" disabled={disabled} className="text-sm text-blue-700" onClick={()=>setSecondVisible(true)}>Добавить основание</button>}
  </div>;
}

export default function PersonnelOrderTransferFields({ value, onChange, orgUnits, currentOrgUnit, departmentSource, validateDepartment=false, departmentPersonNames=[], disabled = false, mode = "transfer", showRates = true, rateOptional = false, showBasis = true, placementLabel, documentFormsKK = false, autoCaseForms=false, autoGenitiveForms=false, onManualEdit, afterDepartment, totalRateOptional=false, onPositionLoadingChange }: {
  value: TransferFields; onChange: React.Dispatch<React.SetStateAction<TransferFields>>; orgUnits: OrgUnitSelectOption[]; disabled?: boolean; mode?: "transfer" | "concurrent" | "cessation"; showRates?: boolean; rateOptional?: boolean; showBasis?: boolean; placementLabel?: string; documentFormsKK?: boolean; autoCaseForms?:boolean; autoGenitiveForms?: boolean; onManualEdit?:(key:keyof TransferFields)=>void;
  currentOrgUnit?: {name?: string | null; name_kk?: string | null} | null;
  departmentSource?: ConcurrentDepartmentSource | null;
  validateDepartment?: boolean; departmentPersonNames?: readonly unknown[];
    afterDepartment?: React.ReactNode;
    totalRateOptional?: boolean;
    onPositionLoadingChange?:(loading:boolean)=>void;
}) {
  const cessation = mode === "cessation";
  const concurrent = mode === "concurrent" || cessation;
  const [positions, setPositions] = React.useState<Option[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const [positionBusy,setPositionBusy]=React.useState(false);
  const [positionError,setPositionError]=React.useState("");
  const requestSequence=React.useRef(0);
  const mounted=React.useRef(true);
  const loadedPosition=React.useRef<number|undefined>(undefined);
  const positionEdits=React.useRef({ru:0,kk:0});
  const lastPositionRequest=React.useRef<{id:number;intent:"mount"|"ru"|"kk"|"restore"}|undefined>(undefined);
  const positionLoadingCallback=React.useRef(onPositionLoadingChange);positionLoadingCallback.current=onPositionLoadingChange;
  React.useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;requestSequence.current++;positionLoadingCallback.current?.(false);};},[]);
  async function readPosition(id:number,intent:"mount"|"ru"|"kk"|"restore"){
    lastPositionRequest.current={id,intent};
    const edits={...positionEdits.current};
    const sequence=++requestSequence.current;setPositionBusy(true);setPositionError("");positionLoadingCallback.current?.(true);
    try{
      const row=await apiFetchJson<TransferPositionRecord>(`/directory/positions/${id}`);
      if(!mounted.current||sequence!==requestSequence.current)return;
      if(row.position_id!==id||!row.name)throw new Error("API вернул другую должность.");
      loadedPosition.current=id;
      setPositions(rows=>[...rows.filter(r=>r.id!==String(id)),{id:String(id),ru:row.name.trim(),kk:row.name_kk?.trim()||""}]);
      onChange(current=>{
        const next=applyTransferPosition(current,row,intent);
        for(const locale of ["ru","kk"] as const)if(positionEdits.current[locale]!==edits[locale]){
          const key=locale==='ru'?'position_ru':'position_kk';next[key]=current[key];next.position_overrides={...next.position_overrides,[locale]:true};
        }
        return next;
      });
    }catch(e){if(mounted.current&&sequence===requestSequence.current)setPositionError(`Не удалось обновить должность: ${e instanceof Error?e.message:"повторите загрузку"}`);}
    finally{if(mounted.current&&sequence===requestSequence.current){setPositionBusy(false);positionLoadingCallback.current?.(false);}}
  }
  React.useEffect(()=>{
    if(!concurrent&&value.position_id&&loadedPosition.current!==value.position_id)void readPosition(value.position_id,"mount");
  },[value.position_id,concurrent]);
  const editedForms=React.useRef(new Set<string>());
  const manualPlacementFields=React.useRef(new Set<string>());
  const selectedOptions=React.useRef<Partial<Record<"position" | "org_unit" | "basis", Option>>>({});
  const previousForms=React.useRef<Record<string,string>>({});
  const previousDepartment=React.useRef<ConcurrentDepartmentSource | null>(null);
  const [repairedSavedDepartment,setRepairedSavedDepartment]=React.useState(false);
  React.useEffect(()=>{
    // Only a clearly invalid saved case of the SAME confirmed transfer unit
    // can be repaired automatically. A different extra unit/manual wording wins.
    if(!validateDepartment || !departmentSource?.org_unit_id || !departmentSource.org_unit_genitive_ru
      || value.org_unit_id!==departmentSource.org_unit_id || value.org_unit_ru!==departmentSource.org_unit_ru
      || editedForms.current.has('org_unit_genitive_ru')
      || !departmentLooksLikePerson(value.org_unit_genitive_ru,departmentPersonNames))return;
    onChange(current=>current.org_unit_id===departmentSource.org_unit_id
      && current.org_unit_ru===departmentSource.org_unit_ru
      && departmentLooksLikePerson(current.org_unit_genitive_ru,departmentPersonNames)
      ? {...current,org_unit_genitive_ru:departmentSource.org_unit_genitive_ru} : current);
    setRepairedSavedDepartment(true);
  },[validateDepartment,departmentSource?.org_unit_id,departmentSource?.org_unit_ru,departmentSource?.org_unit_genitive_ru,value.org_unit_id,value.org_unit_ru,value.org_unit_genitive_ru]);
  React.useEffect(()=>{
    const previous=previousDepartment.current;
    previousDepartment.current=departmentSource || null;
    if(!previous && !departmentSource)return;
    onChange(current=>{
      // Existing saved/additional placement and explicit manual unit names win.
      if((!previous && (current.org_unit_ru.trim() || current.org_unit_kk.trim() || current.org_unit_id))
        || manualPlacementFields.current.has('org_unit_ru') || manualPlacementFields.current.has('org_unit_kk'))return current;
      const ru=refreshAutomaticForm(current.org_unit_ru,previous?.org_unit_ru,departmentSource?.org_unit_ru || '',false);
      const kk=refreshAutomaticForm(current.org_unit_kk,previous?.org_unit_kk,departmentSource?.org_unit_kk || '',false);
      const genitive=refreshAutomaticForm(current.org_unit_genitive_ru || '',previous?.org_unit_genitive_ru,
        departmentSource?.org_unit_genitive_ru || '',editedForms.current.has('org_unit_genitive_ru'));
      if(ru===current.org_unit_ru && kk===current.org_unit_kk && genitive===(current.org_unit_genitive_ru || ''))return current;
      return {...current,org_unit_ru:ru,org_unit_kk:kk,org_unit_genitive_ru:genitive,
        org_unit_id:ru===departmentSource?.org_unit_ru && kk===departmentSource?.org_unit_kk?departmentSource?.org_unit_id:undefined};
    });
  },[departmentSource?.org_unit_ru,departmentSource?.org_unit_kk,departmentSource?.org_unit_genitive_ru,departmentSource?.org_unit_id]);
  React.useEffect(()=>{
    if(!autoCaseForms && !autoGenitiveForms)return;
    const generated={position_genitive_ru:russianReferenceCase(value.position_ru,'genitive'),org_unit_genitive_ru:validateDepartment?concurrentDepartmentGenitive(value.org_unit_ru):russianReferenceCase(value.org_unit_ru,'genitive')};
    const previous=previousForms.current;previousForms.current=generated;
    onChange(current=>{
      const changes:Partial<TransferFields>={};
      for(const key of ['position_genitive_ru','org_unit_genitive_ru'] as const)changes[key]=refreshAutomaticForm(current[key] || "",previous[key],generated[key],editedForms.current.has(key));
      return Object.keys(changes).some(key=>current[key as keyof TransferFields]!==changes[key as keyof TransferFields])?{...current,...changes}:current;
    });
  },[value.position_ru,value.org_unit_ru,autoCaseForms,autoGenitiveForms,validateDepartment]);
  React.useEffect(() => {
    let cancelled = false;
    async function load() {
      const [positionResult] = await Promise.allSettled([
        (async () => {
          const rows: { position_id: number; name: string; name_kk?: string; document_possessive_kk?: string; document_form_status?:string; translation_status?:string }[] = [];
          let offset = 0;
          while (true) {
            const response = await getPositions({ limit: 1000, offset });
            const items = response.items || []; rows.push(...items); offset += items.length;
            if (!items.length || offset >= (response.total ?? offset)) break;
          }
          return rows;
        })(),
      ]);
      if (cancelled) return;
      if (positionResult.status === "fulfilled") setPositions(positionResult.value.map(row => {
        return { id: String(row.position_id), ru: row.name?.trim() || "", kk: concurrent&&row.translation_status==='needs_review' ? '' : row.name_kk?.trim() || "", documentKK: row.document_form_status==='needs_review' ? '' : row.document_possessive_kk?.trim() || "", searchText: row.name?.trim() || "", needsReview:row.document_form_status==='needs_review' };
      }));
      if (positionResult.status === "rejected") setError("Не удалось загрузить справочник должностей RU/KK. Повторно откройте форму или введите недостающие значения вручную.");
      setLoading(false);
    }
    void load();
    return () => { cancelled = true; };
  }, []);
  const units = orgUnits.map(unit => {
    const proposal=autoCaseForms?calculateKazakhOrgUnitGenitive(unit.name_kk):null;
    const documentKK=documentFormsKK ? unit.document_genitive_kk?.trim() || (proposal&&!proposal.needsReview?proposal.value:'') : '';
    return {id:String(unit.unit_id),ru:unit.name.trim(),kk:documentFormsKK && (validateDepartment || autoCaseForms) ? documentKK : documentKK || unit.name_kk?.trim() || '',searchText:unit.name_kk || ''};
  });
  function documentOption(kind: "position" | "org_unit" | "basis", option: Option): Option {
    if(documentFormsKK && kind==='position' && option.needsReview)return {...option,kk:''};
    if (documentFormsKK && kind === "position" && option.documentKK) option = {...option,kk:option.documentKK};
    else if(documentFormsKK&&autoCaseForms&&kind==='position'){
      const proposal=calculateKazakhPositionPossessive(option.kk);
      option={...option,kk:proposal.needsReview?'':proposal.value};
    }
    return option;
  }
  function choose(kind: "position" | "org_unit" | "basis", option: Option, locale: "ru" | "kk", previousText: string) {
    if(kind==='position'&&!concurrent){void readPosition(Number(option.id),locale);return;}
    option = documentOption(kind, option);
    // Selecting a record replaces the selected field. A manual counterpart
    // (including an explicitly cleared value) remains the HR editor's choice.
    manualPlacementFields.current.delete(`${kind}_${locale}`);
    const previousSelection = selectedOptions.current[kind];
    selectedOptions.current[kind] = option;
    const idKey = kind === "basis" ? "basis_type" : `${kind}_id` as "position_id" | "org_unit_id";
    onChange(current => {
      const same = String(current[idKey] ?? previousSelection?.id ?? "") === option.id;
      const formKey=kind === "position" ? "position_genitive_ru" : "org_unit_genitive_ru";
      const records=kind === "position" ? positions : kind === "org_unit" ? units : basisOptions;
      const oldRecord = records.find(row => row.id === String(current[idKey] ?? ""))
        || records.find(row=>documentOption(kind,row)[locale]===previousText);
      const inheritedOption = kind==='org_unit' && departmentSource
        ? {id:String(departmentSource.org_unit_id || ''),ru:departmentSource.org_unit_ru,kk:departmentSource.org_unit_kk} : undefined;
      const oldOption = oldRecord ? documentOption(kind, oldRecord) : previousSelection || inheritedOption;
      const next = (target: "ru" | "kk") => {
        const key = `${kind}_${target}` as "position_ru" | "position_kk";
        const existing = current[key];
        if (target !== locale && kind !== "basis") {
          const savedOverride = Boolean(existing.trim()) && (!oldOption || existing !== oldOption[target]);
          // A saved title of another dictionary unit is a stale linked name,
          // not a custom translation. Explicit manual edits still take priority.
          const staleUnitTitle=kind==='org_unit' && !concurrent && records.some(row=>row[target]===existing);
          if (manualPlacementFields.current.has(key) || (savedOverride && !staleUnitTitle)) return existing;
        }
        if (target !== locale && kind === "basis" && same && existing.trim()) return existing;
        return same && target === locale && !option[target] ? previousText : option[target];
      };
      return { ...current, ...(concurrent && !same && kind !== "basis" && !autoCaseForms && !autoGenitiveForms && !editedForms.current.has(formKey) ? {[formKey]:""} : {}), [idKey]: kind === "basis" ? option.id : Number(option.id),
        [`${kind}_ru`]: next("ru"), [`${kind}_kk`]: next("kk") };
    });
  }
  const repairUnit=orgUnits.find(unit=>(!value.org_unit_id || unit.unit_id===value.org_unit_id) && unit.name.trim().toLocaleLowerCase()===value.org_unit_ru.trim().toLocaleLowerCase());
  const repairedGenitive=concurrentDepartmentGenitive(value.org_unit_ru);
  const canRepairDepartment=validateDepartment && departmentLooksLikePerson(value.org_unit_genitive_ru,departmentPersonNames)
    && !departmentLooksLikePerson(value.org_unit_ru,departmentPersonNames) && Boolean(repairUnit && repairedGenitive);
  const linkedUnit=!concurrent ? orgUnits.find(unit=>unit.unit_id===value.org_unit_id) : undefined;
  const hasManualUnitPair=linkedUnit && (value.org_unit_ru!==linkedUnit.name.trim() || value.org_unit_kk!==(linkedUnit.name_kk?.trim() || ''));
  return <section className="space-y-3 sm:col-span-2" data-testid={concurrent ? "concurrent-fields" : "transfer-fields"}>
    <h3 className="font-medium">{placementLabel ? "Должность и подразделение замещаемого сотрудника" : concurrent ? "Дополнительная занятость при совмещении" : "Данные перевода"}</h3>
    <p className="text-xs">Выберите запись на любом языке — оба названия заполнятся вместе. Недостающий перевод и собственные формулировки можно ввести вручную.</p>
    {!concurrent ? <p className="text-xs" data-testid="transfer-current-unit-hint">Новое подразделение можно не заполнять — сотрудник останется в прежнем подразделении{currentOrgUnit?.name ? `: ${currentOrgUnit.name}` : ""}. При выборе другого подразделения нужны его названия RU и KK.</p> : null}
    {departmentSource && value.org_unit_ru===departmentSource.org_unit_ru ? <p className="text-xs" data-testid="concurrent-department-source">{departmentSource.description}</p> : null}
    {repairedSavedDepartment ? <p role="status" className="text-xs text-amber-700">Сохранённое ФИО в поле подразделения заменено формой подразделения из пункта перевода. Сохраните пункт для обновления текста приказа.</p> : null}
    {hasManualUnitPair ? <p role="status" className="text-xs text-amber-700">Ручное название подразделения сохранено. Чтобы восстановить связанные названия из словаря, <button type="button" disabled={disabled} className="text-blue-700 underline" onClick={()=>{
      manualPlacementFields.current.delete('org_unit_ru');manualPlacementFields.current.delete('org_unit_kk');
      onChange(current=>({...current,org_unit_ru:linkedUnit.name.trim(),org_unit_kk:linkedUnit.name_kk?.trim() || ''}));
    }}>заполните RU и KK по выбранному подразделению</button>.</p> : null}
    {validateDepartment ? concurrentDepartmentErrors(value,departmentPersonNames).map(message=><p key={message} role="alert" className="text-xs text-red-700">{message}</p>) : null}
    {canRepairDepartment ? <button type="button" className="text-sm text-blue-700 underline" disabled={disabled} onClick={()=>{
      editedForms.current.delete('org_unit_genitive_ru');
      onChange(current=>({...current,org_unit_genitive_ru:repairedGenitive,
        org_unit_kk:repairUnit?.document_genitive_kk && (!current.org_unit_kk.trim() || current.org_unit_kk===repairUnit.name_kk || departmentLooksLikePerson(current.org_unit_kk,departmentPersonNames))
          ? repairUnit.document_genitive_kk : current.org_unit_kk}));
    }}>Восстановить формы подразделения по выбранной записи</button> : null}
    {loading ? <p role="status" className="text-xs">Загружается справочник должностей…</p> : null}
    {error ? <p role="alert" className="text-xs text-amber-700">{error}</p> : null}
    {(["position", "org_unit"] as const).flatMap(kind => (["ru", "kk"] as const).map(locale => {
      const key = `${kind}_${locale}` as const;
      return <SearchField key={key} label={`${kind === "position" ? (placementLabel ? `${placementLabel} должность` : concurrent ? "Дополнительная должность" : "Новая должность") : (placementLabel ? `${placementLabel.replace(/ая$/, "ое")} подразделение` : concurrent ? "Дополнительное подразделение" : "Новое подразделение")} (${locale.toUpperCase()})`} value={value[key]} locale={locale} options={kind === "position" ? positions : units} disabled={disabled} onEdit={text => {manualPlacementFields.current.add(key);if(!concurrent&&kind==='position')positionEdits.current[locale]++;onManualEdit?.(key);onChange(current => !concurrent&&kind==='position'?{...current,[key]:text,position_overrides:{...current.position_overrides,[locale]:true}}:({ ...current, [key]: text, [`${kind}_id`]: undefined }));}} onSelect={(option, previousText) => {onManualEdit?.(key);choose(kind, option, locale, previousText);}} />;
    }))}
    {!concurrent&&<div className="space-y-2 text-sm" data-testid="transfer-position-refresh">
      {positionBusy&&<p role="status">Загружаются актуальные данные должности…</p>}
      {positionError&&<p role="alert">{positionError} <button type="button" disabled={disabled||positionBusy||!lastPositionRequest.current} onClick={()=>{const last=lastPositionRequest.current;if(last)void readPosition(last.id,last.intent);}}>Повторить загрузку должности</button></p>}
      {value.position_dictionary&&!value.position_dictionary.name_kk&&<p role="status">В актуальной записи справочника отсутствует name_kk. Перевод можно ввести вручную.</p>}
      {value.position_dictionary?.name_kk&&value.position_dictionary.translation_status!=='confirmed'&&<p role="status">Словарный перевод KK пока не подтверждён.</p>}
      {value.position_overrides?.kk&&<p>KK изменено вручную, включая намеренную очистку. Оно не заменяется автоматически.</p>}
      <button type="button" disabled={disabled||positionBusy||!value.position_id} className="rounded border px-2 py-1" onClick={()=>value.position_id&&void readPosition(value.position_id,"restore")}>Восстановить RU/KK из справочника</button>
      <button type="button" disabled={disabled||positionBusy} className="ml-2 rounded border px-2 py-1" onClick={()=>{positionEdits.current.kk++;onChange(current=>({...current,position_kk:"",position_overrides:{...current.position_overrides,kk:true}}));}}>Очистить KK вручную</button>
    </div>}
    {afterDepartment}
    {validateDepartment && value.org_unit_id && !value.org_unit_kk.trim() ? <p role="status" className="text-xs text-amber-700">Нет подтверждённой формы дополнительного подразделения (KK) для текста приказа. Уточните её вручную.</p> : null}
    {(value.position_id && !value.position_kk.trim()) || (!validateDepartment && value.org_unit_id && !value.org_unit_kk.trim()) ? <p role="status" className="text-xs text-amber-700">{autoCaseForms&&placementLabel?'В справочнике отсутствует казахский перевод выбранной записи. Необязательное поле KK можно оставить пустым или уточнить вручную.':'В справочнике отсутствует казахский перевод выбранной записи. Заполните поле KK вручную.'}</p> : null}
    {concurrent ? <>
      <p className="text-xs">{placementLabel ? "Уточните должность и подразделение замещаемого сотрудника в родительном падеже." : autoCaseForms ? "Дополнительная должность и подразделение необязательны. В распорядительном тексте используются данные назначения получателя." : "Уточните русские названия в родительном падеже для текста приказа. Основная должность в этот текст не подставляется."}</p>
      {([['position_genitive_ru',`${placementLabel || 'Дополнительная'} должность в родительном падеже (RU)`],['org_unit_genitive_ru',`${placementLabel ? placementLabel.replace(/ая$/, 'ое') : 'Дополнительное'} подразделение в родительном падеже (RU)`]] as const).map(([key,label]) => <label key={key} className="block text-sm font-medium">{label}<input aria-label={label} value={value[key] || ""} disabled={disabled} onChange={e => {editedForms.current.add(key);onManualEdit?.(key);onChange(current=>({...current,[key]:e.target.value}));}} className={inputClass}/></label>)}
      {autoGenitiveForms && !rateOptional && (!value.position_genitive_ru || !value.org_unit_genitive_ru) ? <p role="alert" className="text-xs text-amber-700">Нет надёжной формы в родительном падеже для дополнительной должности или подразделения (RU). Заполните недостающее поле вручную.</p> : null}
    </> : null}
    {showRates ? <label className="block text-sm font-medium">{cessation ? "Снимаемая ставка" : concurrent ? "Дополнительная ставка" : "Ставка после перевода"}<input aria-label={cessation ? "Снимаемая ставка" : concurrent ? "Дополнительная ставка" : "Ставка после перевода"} required={!rateOptional} type={mode === "concurrent" && !rateOptional ? "text" : "number"} step="any" inputMode="decimal" value={value.rate} disabled={disabled} onChange={e => onChange(current => ({...current, rate:e.target.value}))} className={inputClass} /></label> : null}
    {concurrent && showRates ? <label className="block text-sm font-medium">{cessation ? "Оставшаяся общая ставка" : "Общая ставка"}{totalRateOptional ? " (необязательно)" : ""}<input aria-label={cessation ? "Оставшаяся общая ставка" : "Общая ставка"} required={!totalRateOptional} type={cessation || rateOptional ? "number" : "text"} step="any" inputMode="decimal" value={(cessation ? value.remaining_rate : value.total_rate) || ""} disabled={disabled} onChange={e=>onChange(current=>({...current,[cessation ? "remaining_rate" : "total_rate"]:e.target.value}))} className={inputClass}/></label> : null}
    {showBasis ? <><p className="text-xs">Выбор формулировки основания не прикрепляет документ. Основания можно уточнить вручную.</p>
    <PersonnelOrderBasisFields value={value} onChange={change=>onChange(current=>({...current,...change}))} disabled={disabled} firstLabel={cessation ? 'Основание прекращения совмещения' : concurrent ? 'Основание совмещения' : 'Основание перевода'} onFirstSelect={(option,locale,previousText)=>choose('basis',option,locale,previousText)}/>
    </> : null}
  </section>;
}
