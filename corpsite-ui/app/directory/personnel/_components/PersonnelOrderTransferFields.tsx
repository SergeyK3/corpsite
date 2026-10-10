"use client";

import * as React from "react";
import { getPositions } from "@/app/directory/employees/_lib/api.client";
import { apiFetchJson } from "@/lib/api";
import type { OrgUnitSelectOption } from "@/lib/orgUnitsSelect";
import {russianReferenceCase} from '../_lib/personnelOrderRussianWording';
import {calculateKazakhOrgUnitGenitive,calculateKazakhPositionPossessive} from '../_lib/kazakhDocumentForms';
import { generatePersonnelOrderBasisText } from "../_lib/personnelOrderBasisGenerate";
import { normalizePersonnelOrderBasisText } from "../_lib/personnelOrderBasisText";
import type { PersonnelOrderBasisType } from "../_lib/personnelOrderEditorialTypes";

export type TransferFields = {
  position_ru: string; position_kk: string; org_unit_ru: string; org_unit_kk: string;
  rate: string; basis_ru: string; basis_kk: string;
  position_genitive_ru?: string; org_unit_genitive_ru?: string; total_rate?: string; remaining_rate?: string; assignment_id?: number;
  position_id?: number; org_unit_id?: number; basis_type?: PersonnelOrderBasisType;
};
type Option = { id: string; ru: string; kk: string; documentKK?: string; searchText?: string };
type Job = { job_nameru?: string; job_namekk?: string; job_namekk_doc?: string; legacy_position_ids?: number[] };
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

export default function PersonnelOrderTransferFields({ value, onChange, orgUnits, disabled = false, mode = "transfer", showRates = true, showBasis = true, placementLabel, documentFormsKK = false, autoCaseForms=false, onManualEdit }: {
  value: TransferFields; onChange: React.Dispatch<React.SetStateAction<TransferFields>>; orgUnits: OrgUnitSelectOption[]; disabled?: boolean; mode?: "transfer" | "concurrent" | "cessation"; showRates?: boolean; showBasis?: boolean; placementLabel?: string; documentFormsKK?: boolean; autoCaseForms?:boolean; onManualEdit?:(key:keyof TransferFields)=>void;
}) {
  const cessation = mode === "cessation";
  const concurrent = mode === "concurrent" || cessation;
  const [positions, setPositions] = React.useState<Option[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState("");
  const editedForms=React.useRef(new Set<string>());
  const previousForms=React.useRef<Record<string,string>>({});
  React.useEffect(()=>{
    if(!autoCaseForms)return;
    const generated={position_genitive_ru:russianReferenceCase(value.position_ru,'genitive'),org_unit_genitive_ru:russianReferenceCase(value.org_unit_ru,'genitive')};
    const previous=previousForms.current;previousForms.current=generated;
    onChange(current=>{
      const changes:Partial<TransferFields>={};
      for(const key of ['position_genitive_ru','org_unit_genitive_ru'] as const)if(!editedForms.current.has(key)&&(!current[key]||current[key]===previous[key]))changes[key]=generated[key];
      return Object.keys(changes).some(key=>current[key as keyof TransferFields]!==changes[key as keyof TransferFields])?{...current,...changes}:current;
    });
  },[value.position_ru,value.org_unit_ru,autoCaseForms]);
  React.useEffect(() => {
    let cancelled = false;
    async function load() {
      const [positionResult, jobResult] = await Promise.allSettled([
        (async () => {
          const rows: { position_id: number; name: string; name_kk?: string; document_possessive_kk?: string }[] = [];
          let offset = 0;
          while (true) {
            const response = await getPositions({ limit: 1000, offset });
            const items = response.items || []; rows.push(...items); offset += items.length;
            if (!items.length || offset >= (response.total ?? offset)) break;
          }
          return rows;
        })(),
        apiFetchJson<{ items: Job[] }>("/directory/job-positions"),
      ]);
      if (cancelled) return;
      const jobs = new Map<number, Job>();
      if (jobResult.status === "fulfilled") for (const job of jobResult.value.items) for (const id of job.legacy_position_ids || []) jobs.set(id, job);
      if (positionResult.status === "fulfilled") setPositions(positionResult.value.map(row => {
        const job = jobs.get(row.position_id);
        return { id: String(row.position_id), ru: job?.job_nameru?.trim() || row.name?.trim() || "", kk: job?.job_namekk?.trim() || row.name_kk?.trim() || "", documentKK: job?.job_namekk_doc?.trim() || row.document_possessive_kk?.trim() || "", searchText: row.name?.trim() || "" };
      }));
      if (positionResult.status === "rejected" || jobResult.status === "rejected") setError("Не удалось загрузить весь справочник должностей RU/KK. Повторно откройте форму или введите недостающие значения вручную.");
      setLoading(false);
    }
    void load();
    return () => { cancelled = true; };
  }, []);
  const units = orgUnits.map(unit => ({ id: String(unit.unit_id), ru: unit.name.trim(), kk: (documentFormsKK ? unit.document_genitive_kk?.trim() || (autoCaseForms?calculateKazakhOrgUnitGenitive(unit.name_kk).value:'') : "") || unit.name_kk?.trim() || "" }));
  function choose(kind: "position" | "org_unit" | "basis", option: Option, locale: "ru" | "kk", previousText: string) {
    if (documentFormsKK && kind === "position" && option.documentKK) option = {...option,kk:option.documentKK};
    else if(documentFormsKK&&autoCaseForms&&kind==='position')option={...option,kk:calculateKazakhPositionPossessive(option.kk).value};
    const idKey = kind === "basis" ? "basis_type" : `${kind}_id` as "position_id" | "org_unit_id";
    onChange(current => {
      const same = String(current[idKey] ?? "") === option.id;
      const formKey=kind === "position" ? "position_genitive_ru" : "org_unit_genitive_ru";
      return { ...current, ...(concurrent && !same && kind !== "basis" && (!autoCaseForms||!editedForms.current.has(formKey)) ? {[formKey]:autoCaseForms?russianReferenceCase(option.ru,'genitive'):""} : {}), [idKey]: kind === "basis" ? option.id : Number(option.id),
        [`${kind}_ru`]: same && locale !== "ru" && current[`${kind}_ru`].trim() ? current[`${kind}_ru`] : (same && locale === "ru" && !option.ru ? previousText : option.ru),
        [`${kind}_kk`]: same && locale !== "kk" && current[`${kind}_kk`].trim() ? current[`${kind}_kk`] : (same && locale === "kk" && !option.kk ? previousText : option.kk) };
    });
  }
  return <section className="space-y-3 sm:col-span-2" data-testid={concurrent ? "concurrent-fields" : "transfer-fields"}>
    <h3 className="font-medium">{placementLabel ? "Должность и подразделение замещаемого сотрудника" : concurrent ? "Дополнительная занятость при совмещении" : "Данные перевода"}</h3>
    <p className="text-xs">Выберите запись на любом языке — оба названия заполнятся вместе. Недостающий перевод и собственные формулировки можно ввести вручную.</p>
    {loading ? <p role="status" className="text-xs">Загружается справочник должностей…</p> : null}
    {error ? <p role="alert" className="text-xs text-amber-700">{error}</p> : null}
    {(["position", "org_unit"] as const).flatMap(kind => (["ru", "kk"] as const).map(locale => {
      const key = `${kind}_${locale}` as const;
      return <SearchField key={key} label={`${kind === "position" ? (placementLabel ? `${placementLabel} должность` : concurrent ? "Дополнительная должность" : "Новая должность") : (placementLabel ? `${placementLabel.replace(/ая$/, "ое")} подразделение` : concurrent ? "Дополнительное подразделение" : "Новое подразделение")} (${locale.toUpperCase()})`} value={value[key]} locale={locale} options={kind === "position" ? positions : units} disabled={disabled} onEdit={text => {onManualEdit?.(key);onChange(current => ({ ...current, [key]: text }));}} onSelect={(option, previousText) => {onManualEdit?.(key);choose(kind, option, locale, previousText);}} />;
    }))}
    {(value.position_id && !value.position_kk.trim()) || (value.org_unit_id && !value.org_unit_kk.trim()) ? <p role="status" className="text-xs text-amber-700">{autoCaseForms&&placementLabel?'В справочнике отсутствует казахский перевод выбранной записи. Необязательное поле KK можно оставить пустым или уточнить вручную.':'В справочнике отсутствует казахский перевод выбранной записи. Заполните поле KK вручную.'}</p> : null}
    {concurrent ? <>
      <p className="text-xs">{placementLabel ? "Уточните должность и подразделение замещаемого сотрудника в родительном падеже." : autoCaseForms ? "Дополнительная должность и подразделение необязательны. В распорядительном тексте используются данные назначения получателя." : "Уточните русские названия в родительном падеже для текста приказа. Основная должность в этот текст не подставляется."}</p>
      {([['position_genitive_ru',`${placementLabel || 'Дополнительная'} должность в родительном падеже (RU)`],['org_unit_genitive_ru',`${placementLabel ? placementLabel.replace(/ая$/, 'ое') : 'Дополнительное'} подразделение в родительном падеже (RU)`]] as const).map(([key,label]) => <label key={key} className="block text-sm font-medium">{label}<input aria-label={label} value={value[key] || ""} disabled={disabled} onChange={e => {editedForms.current.add(key);onManualEdit?.(key);onChange(current=>({...current,[key]:e.target.value}));}} className={inputClass}/></label>)}
    </> : null}
    {showRates ? <label className="block text-sm font-medium">{cessation ? "Снимаемая ставка" : concurrent ? "Дополнительная ставка" : "Ставка после перевода"}<input aria-label={cessation ? "Снимаемая ставка" : concurrent ? "Дополнительная ставка" : "Ставка после перевода"} required type="number" step="any" value={value.rate} disabled={disabled} onChange={e => onChange(current => ({...current, rate:e.target.value}))} className={inputClass} /></label> : null}
    {concurrent && showRates ? <label className="block text-sm font-medium">{cessation ? "Оставшаяся общая ставка" : "Общая ставка"}<input aria-label={cessation ? "Оставшаяся общая ставка" : "Общая ставка"} required type="number" step="any" value={(cessation ? value.remaining_rate : value.total_rate) || ""} disabled={disabled} onChange={e=>onChange(current=>({...current,[cessation ? "remaining_rate" : "total_rate"]:e.target.value}))} className={inputClass}/></label> : null}
    {showBasis ? <><p className="text-xs">Выбор формулировки основания не прикрепляет документ. Основания можно уточнить вручную.</p>
    {(["ru", "kk"] as const).map(locale => <SearchField key={locale} label={`${cessation ? "Основание прекращения совмещения" : concurrent ? "Основание совмещения" : "Основание перевода"} (${locale.toUpperCase()})`} value={value[`basis_${locale}`]} locale={locale} options={basisOptions} disabled={disabled} onEdit={text => onChange(current => ({ ...current, [`basis_${locale}`]: text }))} onSelect={(option, previousText) => choose("basis", option, locale, previousText)} />)}
    </> : null}
  </section>;
}
