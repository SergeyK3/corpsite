"use client";
import { switchServiceLengthSubject, type ServiceLengthDraft } from "../_lib/serviceLengthDraft";

export default function PersonnelOrderServiceLengthFields({ value, onChange, disabled = false }: {
  value: ServiceLengthDraft; onChange: (value: ServiceLengthDraft) => void; disabled?: boolean;
}) {
  const input = (label: string, text: string, change: (text: string) => void, type = "text") => <label className="block space-y-1">
    <span>{label}</span><input aria-label={label} required type={type} value={text} onChange={event => change(event.target.value)} className="block w-full rounded border bg-transparent p-2" />
  </label>;
  return <fieldset disabled={disabled} data-testid="order-service-length-fields" className="space-y-3 rounded border p-3 sm:col-span-2">
    <legend>Изменение стажа</legend>
    <div role="radiogroup" aria-label="Способ указания сотрудника" className="flex flex-wrap gap-4">
      {([["DIRECTORY", "Выбрать из списка"], ["MANUAL", "Ввести вручную"]] as const).map(([mode, label]) => <label key={mode} className="flex items-center gap-2">
        <input type="radio" name="service-length-subject-mode" value={mode} checked={(value.subject_mode || "DIRECTORY") === mode} onChange={() => onChange(switchServiceLengthSubject(value, mode))} />{label}
      </label>)}
    </div>
    {value.subject_mode === "MANUAL" ? <>
      {input("ФИО сотрудника вручную", value.source_employee_name, source_employee_name => onChange({ ...value, source_employee_name }))}
      <p className="text-xs">ФИО и формы RU/KK сохраняются в приказе. Склонения автоматически не вычисляются; карточка сотрудника не создаётся.</p>
    </> : null}
    {input("ФИО в родительном падеже RU", value.document_forms_ru.employee_full_name_genitive_ru, text => onChange({ ...value, document_forms_ru: { ...value.document_forms_ru, employee_full_name_genitive_ru: text } }))}
    {input("ФИО в ілік септік KK", value.document_forms_kk.employee_full_name_genitive_kk, text => onChange({ ...value, document_forms_kk: { ...value.document_forms_kk, employee_full_name_genitive_kk: text } }))}
    {input("Должность в родительном падеже RU", value.document_forms_ru.position_document_genitive_ru, text => onChange({ ...value, document_forms_ru: { ...value.document_forms_ru, position_document_genitive_ru: text } }))}
    {input("Должность в тексте KK", value.document_forms_kk.position_document_possessive_kk, text => onChange({ ...value, document_forms_kk: { ...value.document_forms_kk, position_document_possessive_kk: text } }))}
    {input("Подразделение в родительном падеже RU", value.document_org_unit.document_genitive_ru, text => onChange({ ...value, document_org_unit: { ...value.document_org_unit, document_genitive_ru: text } }))}
    {input("Подразделение в ілік септік KK", value.document_org_unit.document_genitive_kk, text => onChange({ ...value, document_org_unit: { ...value.document_org_unit, document_genitive_kk: text } }))}
    {input("Дата начала действия", value.effective_date, effective_date => onChange({ ...value, effective_date }), "date")}
    {(["ru", "kk"] as const).map(locale => <div key={locale} className="space-y-3">
      {input(`Новый стаж ${locale.toUpperCase()}`, value.service_length[`new_${locale}`], text => onChange({ ...value, service_length: { ...value.service_length, [`new_${locale}`]: text } }))}
      <label className="block">Основание {locale.toUpperCase()}<textarea aria-label={`Основание ${locale.toUpperCase()}`} required value={value.basis[locale]} onChange={event => onChange({ ...value, basis: { ...value.basis, [locale]: event.target.value } })} className="block w-full rounded border bg-transparent p-2" /></label>
    </div>)}
    <p className="text-xs">Новый стаж и основание вводятся вручную отдельно на RU и KK. Система не рассчитывает стаж по датам и не выводит его автоматически. Дата начала действия указывается отдельно.</p>
  </fieldset>;
}
