"use client";
import { switchEducationSubject, type EducationDraft } from "../_lib/educationDraft";
import { useEducationOrderCatalogs, type EducationOrderReference } from "../_lib/educationOrderCatalogs";
import { usePersonnelOrderPositions } from "../_lib/personnelOrderPositions";
import PersonnelOrderPositionPicker from "./PersonnelOrderPositionPicker";

export default function PersonnelOrderEducationFields({ value, onChange, disabled = false }: {
  value: EducationDraft; onChange: (value: EducationDraft) => void; disabled?: boolean;
}) {
  const catalogs = useEducationOrderCatalogs();
  const positions = usePersonnelOrderPositions(!disabled);
  const pair = (title: string, rows: EducationOrderReference[], ru: string, kk: string, code: string | null | undefined,
    required: boolean, change: (row: EducationOrderReference | null) => void) => {
    // Snapshots stay authoritative, even after a catalog rename or deactivation.
    const selected = rows.find(row => (!code || row.code === code) && row.name_ru === ru && (row.name_kk || "") === kk);
    const key = selected?.code || (ru || kk ? "__saved__" : "");
    return <div className="grid gap-3 sm:grid-cols-2">
      {(["ru", "kk"] as const).map(locale => <label key={locale} className="block space-y-1">
        <span>{title} {locale.toUpperCase()}{required ? "" : " (необязательно)"}</span>
        <select aria-label={`${title} ${locale.toUpperCase()}`} required={required} value={key} className="block w-full rounded border bg-transparent p-2" onChange={event => {
          if (event.target.value === "__saved__") return;
          change(rows.find(row => row.code === event.target.value) || null);
        }}>
          <option value="">Не указано</option>
          {key === "__saved__" ? <option value="__saved__">{(locale === "ru" ? ru : kk) || "Нет названия в справочнике"} (сохранённое значение)</option> : null}
          {rows.map(row => <option key={row.code} value={row.code}>{(locale === "ru" ? row.name_ru : row.name_kk) || `${row.name_ru} — нет названия KK`}</option>)}
        </select>
      </label>)}
    </div>;
  };
  const unitSelect = (locale: "ru" | "kk") => {
    const current = value.document_org_unit;
    const selected = catalogs.units.find(row => row.unit_id === current.unit_id && row.name === current.name && (row.name_kk || "") === current.name_kk);
    return <label className="block space-y-1"><span>Выбрать подразделение {locale.toUpperCase()}</span>
      <select aria-label={`Выбрать подразделение ${locale.toUpperCase()}`} value={selected?.unit_id || (current.name || current.name_kk ? "__saved__" : "")} className="block w-full rounded border bg-transparent p-2" onChange={event => {
        if (event.target.value === "__saved__") return;
        const unit = catalogs.units.find(row => row.unit_id === Number(event.target.value));
        onChange({ ...value, document_org_unit: { unit_id: unit?.unit_id || null, name: unit?.name || "", name_kk: unit?.name_kk || "", document_genitive_ru: unit?.document_genitive_ru || "", document_genitive_kk: unit?.document_genitive_kk || "" } });
      }}>
        <option value="">Не указано</option>
        {!selected && (current.name || current.name_kk) ? <option value="__saved__">{(locale === "ru" ? current.name : current.name_kk) || "Нет названия"} (сохранённое значение)</option> : null}
        {catalogs.units.map(unit => <option key={unit.unit_id} value={unit.unit_id}>{(locale === "ru" ? unit.name : unit.name_kk) || `${unit.name} — нет названия KK`}</option>)}
      </select>
    </label>;
  };
  const input = (label: string, text: string, change: (text: string) => void, type = "text", required = true) => <label className="block space-y-1">
    <span>{label}</span><input aria-label={label} required={required} type={type} value={text} onChange={event => change(event.target.value)} className="block w-full rounded border bg-transparent p-2" />
  </label>;
  return <fieldset disabled={disabled} data-testid="order-education-fields" className="space-y-3 rounded border p-3 sm:col-span-2">
    <legend>Изменение информации об образовании</legend>
    {catalogs.loading ? <p role="status">Загружаются справочники…</p> : null}
    {catalogs.errors.map(error => <p key={error} role="alert">{error}</p>)}
    <div role="radiogroup" aria-label="Способ указания сотрудника" className="flex flex-wrap gap-4">
      {([["DIRECTORY", "Выбрать из списка"], ["MANUAL", "Ввести вручную"]] as const).map(([mode, label]) => <label key={mode} className="flex items-center gap-2">
        <input type="radio" name="education-subject-mode" checked={(value.subject_mode || "DIRECTORY") === mode} onChange={() => onChange(switchEducationSubject(value, mode))} />{label}
      </label>)}
    </div>
    {value.subject_mode === "MANUAL" ? input("ФИО сотрудника вручную", value.source_employee_name, source_employee_name => onChange({ ...value, source_employee_name })) : null}
    <p className="text-xs">Сохранённые формы подставляются при выборе сотрудника. Недостающие формы заполните вручную. Автоматическое склонение и перевод не выполняются; поля можно исправить.</p>
    {input("ФИО в родительном падеже RU", value.document_forms_ru.employee_full_name_genitive_ru, text => onChange({ ...value, document_forms_ru: { ...value.document_forms_ru, employee_full_name_genitive_ru: text } }))}
    {input("ФИО в ілік септік KK", value.document_forms_kk.employee_full_name_genitive_kk, text => onChange({ ...value, document_forms_kk: { ...value.document_forms_kk, employee_full_name_genitive_kk: text } }))}
    <label className="block space-y-1"><span>Должность RU</span><PersonnelOrderPositionPicker label="Должность RU" value={value.source_position_name} {...positions}
      onCustomChange={source_position_name => onChange({ ...value, source_position_id: null, source_position_name })}
      onSelect={position => onChange({ ...value, source_position_id: position.id, source_position_name: position.document_nominative_ru || position.name,
        source_position_name_kk: position.name_kk || "",
        document_forms_ru: { ...value.document_forms_ru, position_document_genitive_ru: position.document_genitive_ru || "" },
        document_forms_kk: { ...value.document_forms_kk, position_document_possessive_kk: position.document_possessive_kk || "" } })} /></label>
    {input("Должность KK", value.source_position_name_kk, source_position_name_kk => onChange({ ...value, source_position_name_kk }), "text", false)}
    {input("Должность в родительном падеже RU", value.document_forms_ru.position_document_genitive_ru, text => onChange({ ...value, document_forms_ru: { ...value.document_forms_ru, position_document_genitive_ru: text } }))}
    {input("Должность в тексте KK", value.document_forms_kk.position_document_possessive_kk, text => onChange({ ...value, document_forms_kk: { ...value.document_forms_kk, position_document_possessive_kk: text } }))}
    <p className="text-xs">«Должность KK» — название; «Должность в тексте KK» — сохранённая притяжательная форма для приказа. Эти значения могут различаться.</p>
    <div className="grid gap-3 sm:grid-cols-2">{unitSelect("ru")}{unitSelect("kk")}</div>
    {input("Подразделение RU", value.document_org_unit.name, name => onChange({ ...value, document_org_unit: { ...value.document_org_unit, name } }), "text", false)}
    {input("Подразделение KK", value.document_org_unit.name_kk, name_kk => onChange({ ...value, document_org_unit: { ...value.document_org_unit, name_kk } }), "text", false)}
    {input("Подразделение в родительном падеже RU", value.document_org_unit.document_genitive_ru, text => onChange({ ...value, document_org_unit: { ...value.document_org_unit, document_genitive_ru: text } }))}
    {input("Подразделение в ілік септік KK", value.document_org_unit.document_genitive_kk, text => onChange({ ...value, document_org_unit: { ...value.document_org_unit, document_genitive_kk: text } }))}
    {input("Дата начала действия", value.effective_date, effective_date => onChange({ ...value, effective_date }), "date")}
    {pair("Уровень образования", catalogs.levels, value.education.level_ru, value.education.level_kk, value.education.level_code, false, row => onChange({ ...value, education: { ...value.education, level_code: row?.code || null, level_ru: row?.name_ru || "", level_kk: row?.name_kk || "" } }))}
    {pair("Специальность", catalogs.specialties, value.education.specialty_ru, value.education.specialty_kk, value.education.medical_specialty_id == null ? null : String(value.education.medical_specialty_id), false, row => onChange({ ...value, education: { ...value.education, medical_specialty_id: row ? Number(row.code) : null, specialty_ru: row?.name_ru || "", specialty_kk: row?.name_kk || "" } }))}
    <p className="text-xs">Пустой уровень образования означает «не указано», а «Без образования» — отдельное значение. Если у специальности нет названия KK, оно остаётся пустым; перевод не создаётся.</p>
    {pair("Вид документа", catalogs.kinds, value.education_document.kind_ru, value.education_document.kind_kk, value.education_document.kind_code, true, row => onChange({ ...value, education_document: { ...value.education_document, kind_code: row?.code || null, kind_ru: row?.name_ru || "", kind_kk: row?.name_kk || "" } }))}
    {input("Номер документа", value.education_document.number, number => onChange({ ...value, education_document: { ...value.education_document, number } }))}
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="block space-y-1"><span>Состояние даты выдачи документа</span>
        <select aria-label="Состояние даты выдачи документа" value={value.education_document.issued_at_status || "KNOWN"} className="block w-full rounded border bg-transparent p-2"
          onChange={event => onChange({ ...value, education_document: { ...value.education_document, issued_at_status: event.target.value as "KNOWN" | "TO_CLARIFY", issued_at: "" } })}>
          <option value="KNOWN">Указать дату</option><option value="TO_CLARIFY">Уточнить</option>
        </select>
      </label>
      <label className="block space-y-1"><span>Дата выдачи документа</span>
        <input aria-label="Дата выдачи документа" type="date" required={value.education_document.issued_at_status !== "TO_CLARIFY"}
          disabled={value.education_document.issued_at_status === "TO_CLARIFY"} value={value.education_document.issued_at}
          onChange={event => onChange({ ...value, education_document: { ...value.education_document, issued_at: event.target.value } })}
          className="block w-full rounded border bg-transparent p-2 disabled:opacity-50" />
      </label>
    </div>
    {value.education_document.issued_at_status === "TO_CLARIFY" ? <p className="text-sm">Дата выдачи: Уточнить. Дата не задана; в предпросмотре — «Уточнить» / «Нақтылау қажет».</p> : null}
  </fieldset>;
}
