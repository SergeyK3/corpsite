"use client";
import * as React from "react";
import {apiFetchJson} from "@/lib/api";
import type {EducationOrderReference} from "../_lib/educationOrderCatalogs";
import {hireYearsError, normalizeHireYears, type HireDetails} from "../_lib/personnelOrderHireDetails";
import PersonnelOrderHireCertificateSpecialtyFields from './PersonnelOrderHireCertificateSpecialtyFields';

export default function PersonnelOrderHireDetailsFields({value, onChange, disabled = false}: {
  value: HireDetails; onChange: (value: HireDetails) => void; disabled?: boolean;
}) {
  const [levels, setLevels] = React.useState<EducationOrderReference[]>([]);
  const [error, setError] = React.useState(false);
  const yearsInput = React.useRef<HTMLInputElement>(null);
  React.useEffect(() => {yearsInput.current?.setCustomValidity(hireYearsError(value.service_length_years ?? ""));}, [value.service_length_years]);
  React.useEffect(() => {
    let live = true;
    void apiFetchJson<{items: EducationOrderReference[]; schema_ready: boolean}>("/api/ppr/education-levels", {query: {state: "active"}})
      .then(result => {
        if (!result.schema_ready) throw Error("Education classifier unavailable");
        if (live) setLevels(result.items.filter(row => row.is_active));
      }).catch(() => {if (live) setError(true);});
    return () => {live = false;};
  }, []);
  const selected = levels.find(row => row.code === value.education.code && row.name_ru === value.education.ru && (row.name_kk || "") === value.education.kk);
  const saved = !selected && Boolean(value.education.code || value.education.ru || value.education.kk);
  return <fieldset disabled={disabled} aria-label="Дополнительные сведения пункта" className="space-y-3 rounded border p-3 sm:col-span-2" data-testid="hire-details-fields">
    <label className="block space-y-1"><span>Образование / Білімі</span>
      <select aria-label="Образование / Білімі" value={selected?.code || (saved ? "__saved__" : "")} className="block w-full rounded border bg-transparent p-2" onChange={event => {
        if (event.target.value === "__saved__") return;
        const row = levels.find(row => row.code === event.target.value);
        onChange({...value, education: {code: row?.code || "", ru: row?.name_ru || "", kk: row?.name_kk || ""}});
      }}>
        <option value="">Не указано / Көрсетілмеген</option>
        {saved ? <option value="__saved__">{[value.education.ru, value.education.kk].filter(Boolean).join(" / ")} (сохранено)</option> : null}
        {levels.map(row => <option key={row.code} value={row.code}>{[row.name_ru, row.name_kk].filter(Boolean).join(" / ")}</option>)}
      </select>
    </label>
    {error ? <p role="alert" className="text-sm text-amber-700">Не удалось загрузить уровни образования. Сохранённое значение оставлено без изменений.</p> : null}
    <fieldset className="space-y-3 rounded border p-3" data-testid="hire-certificate-fields"><legend>Сертификат (необязательно)</legend>
      <PersonnelOrderHireCertificateSpecialtyFields value={value.certificate} disabled={disabled}
        onChange={certificate=>onChange({...value,certificate})}/>
      <label className="block space-y-1"><span>Дата выдачи сертификата</span><input aria-label="Дата выдачи сертификата" type="date"
        value={value.certificate?.issued_on||''} onChange={event=>onChange({...value,certificate:{...value.certificate,specialty:value.certificate?.specialty||null,issued_on:event.target.value}})}
        className="block w-full rounded border bg-transparent p-2"/></label>
    </fieldset>
    <label className="block space-y-1"><span>Трудовой стаж, лет</span>
      <input ref={yearsInput} aria-label="Трудовой стаж, лет" type="text" inputMode="decimal" pattern="[0-9]+([,.][0-9]+)?"
        value={(value.service_length_years ?? "").replace(".", ",")} className="block w-full rounded border bg-transparent p-2"
        onChange={event => {
          const years = event.target.value.replaceAll(".", ",");
          event.currentTarget.setCustomValidity(hireYearsError(years));
          onChange({...value, service_length_years: years});
        }} onBlur={() => {
          if (value.service_length_years !== undefined && !hireYearsError(value.service_length_years))
            onChange({...value, service_length_years: normalizeHireYears(value.service_length_years).replace(".", ",")});
        }} />
    </label>
    {value.service_length.ru || value.service_length.kk ? <p className="text-sm text-zinc-500" data-testid="hire-legacy-tenure">
      Прежний текст стажа сохранён без преобразования: {[value.service_length.ru, value.service_length.kk].filter(Boolean).join(" / ")}
    </p> : null}
  </fieldset>;
}
