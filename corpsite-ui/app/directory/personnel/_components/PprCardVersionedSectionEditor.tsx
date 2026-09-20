"use client";

import * as React from "react";

import {
  createPprCardRecord,
  supersedePprCardRecord,
  voidPprCardRecord,
} from "../_lib/pprQueryApi.client";
import type {
  PprEducationRecordResponse,
  PprRelativeRecordResponse,
  PprTrainingRecordResponse,
} from "../_lib/pprQueryTypes";

type Section = "education" | "training" | "relatives";
type RecordValue = PprEducationRecordResponse | PprTrainingRecordResponse | PprRelativeRecordResponse;
type SelectOption = { value: string; label: string };
type Field = { key: string; label: string; required?: boolean; type?: "date" | "number"; options?: readonly SelectOption[] };

const EDUCATION_KIND_OPTIONS: readonly SelectOption[] = [
  { value: "basic", label: "Основное образование" },
  { value: "internship", label: "Интернатура" },
  { value: "residency", label: "Резидентура" },
  { value: "masters", label: "Магистратура" },
  { value: "phd", label: "Докторантура (PhD)" },
  { value: "other", label: "Другое" },
];

const INSTITUTION_TYPE_OPTIONS: readonly SelectOption[] = [
  { value: "university", label: "ВУЗ (университет, академия, институт)" },
  { value: "college", label: "Колледж / училище" },
  { value: "other", label: "Другое" },
  { value: "unknown", label: "Не указано" },
];

const FIELDS: Record<Section, Field[]> = {
  education: [
    { key: "education_kind", label: "Вид образования", required: true, options: EDUCATION_KIND_OPTIONS },
    { key: "institution_type", label: "Тип учреждения", options: INSTITUTION_TYPE_OPTIONS },
    { key: "institution_name", label: "Учебное заведение" },
    { key: "specialty", label: "Специальность" },
    { key: "qualification", label: "Квалификация" },
    { key: "started_at", label: "Начало", type: "date" },
    { key: "completed_at", label: "Окончание", type: "date" },
    { key: "diploma_number", label: "Номер диплома" },
    { key: "document_date", label: "Дата документа", type: "date" },
  ],
  training: [
    { key: "training_kind", label: "Вид обучения", required: true },
    { key: "title", label: "Наименование" },
    { key: "organization_name", label: "Организация" },
    { key: "hours", label: "Часы", type: "number" },
    { key: "started_at", label: "Начало", type: "date" },
    { key: "completed_at", label: "Окончание", type: "date" },
    { key: "certificate_number", label: "Номер сертификата" },
    { key: "document_date", label: "Дата документа", type: "date" },
  ],
  relatives: [
    { key: "relationship_type", label: "Степень родства", required: true },
    { key: "full_name", label: "Ф.И.О.", required: true },
    { key: "birth_date", label: "Дата рождения", type: "date" },
    { key: "birth_place", label: "Место рождения" },
    { key: "organization_name", label: "Организация" },
    { key: "residence_address", label: "Адрес" },
    { key: "notes", label: "Примечание" },
  ],
};

function emptyValues(section: Section): Record<string, string> {
  return Object.fromEntries(FIELDS[section].map((field) => [field.key, ""]));
}

function valuesFromRecord(section: Section, record: RecordValue): Record<string, string> {
  const source = record as unknown as Record<string, unknown>;
  return Object.fromEntries(FIELDS[section].map((field) => [field.key, source[field.key] == null ? "" : String(source[field.key])])) ;
}

function payloadFor(section: Section, values: Record<string, string>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const field of FIELDS[section]) {
    const value = values[field.key]?.trim() ?? "";
    if (field.required && !value) throw new Error(`Заполните поле «${field.label}».`);
    result[field.key] = field.type === "number" ? (value === "" ? null : Number(value)) : (value || null);
  }
  return result;
}

function commandId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

export default function PprCardVersionedSectionEditor({
  personId,
  section,
  active,
  onSaved,
}: {
  personId: number;
  section: Section;
  active: RecordValue[];
  onSaved: () => void;
}) {
  const [editing, setEditing] = React.useState<RecordValue | null | undefined>(undefined);
  const [values, setValues] = React.useState<Record<string, string>>(() => emptyValues(section));
  const [voiding, setVoiding] = React.useState<RecordValue | null>(null);
  const [reason, setReason] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const dirty = editing !== undefined || voiding !== null;
  React.useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const cancel = () => { setEditing(undefined); setVoiding(null); setError(null); setReason(""); };
  const startCreate = () => { setError(null); setValues(emptyValues(section)); setEditing(null); };
  const startEdit = (record: RecordValue) => { setError(null); setValues(valuesFromRecord(section, record)); setEditing(record); };
  const save = async () => {
    setSaving(true); setError(null);
    try {
      const record = payloadFor(section, values);
      if (editing && editing.record_id != null && editing.updated_at) {
        await supersedePprCardRecord(personId, section, editing.record_id, {
          command_id: commandId(), expected_updated_at: editing.updated_at, replacement: record,
        });
      } else {
        await createPprCardRecord(personId, section, { command_id: commandId(), record });
      }
      cancel(); onSaved();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Не удалось сохранить запись.";
      setError(/409|conflict|изменен/i.test(message) ? "Запись уже изменилась другим пользователем. Обновите карточку и повторите действие." : message);
    } finally { setSaving(false); }
  };
  const confirmVoid = async () => {
    if (!voiding?.record_id || !voiding.updated_at) return;
    if (!reason.trim()) { setError("Укажите причину удаления."); return; }
    setSaving(true); setError(null);
    try {
      await voidPprCardRecord(personId, section, voiding.record_id, { command_id: commandId(), expected_updated_at: voiding.updated_at, reason: reason.trim() });
      cancel(); onSaved();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Не удалось удалить запись.";
      setError(/409|conflict|изменен/i.test(message) ? "Запись уже изменилась другим пользователем. Обновите карточку и повторите действие." : message);
    } finally { setSaving(false); }
  };

  return <div className="mt-3 space-y-3 rounded-lg border border-blue-200 bg-blue-50/50 p-3 dark:border-blue-900 dark:bg-blue-950/20" data-testid={`ppr-${section}-editor`}>
    {error ? <p role="alert" className="text-sm text-red-700 dark:text-red-300">{error}</p> : null}
    {editing === undefined && voiding === null ? <>
      <div className="flex flex-wrap gap-2"><button type="button" className="rounded border px-3 py-1 text-sm" onClick={startCreate}>Добавить запись</button></div>
      {active.map((record) => record.record_id != null ? <div key={record.record_id} className="flex flex-wrap items-center gap-2 text-sm">
        <span>Запись #{record.record_id}</span><button type="button" className="rounded border px-2 py-1" onClick={() => startEdit(record)}>Редактировать</button><button type="button" className="rounded border border-red-300 px-2 py-1 text-red-700" onClick={() => { setError(null); setVoiding(record); }}>Удалить</button>
      </div> : null)}
    </> : null}
    {editing !== undefined ? <div className="grid gap-2 sm:grid-cols-2">
      {FIELDS[section].map((field) => <label key={field.key} className="text-sm">{field.label}{field.required ? " *" : ""}{field.options ? <select aria-label={field.label} value={values[field.key] ?? ""} onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))} className="mt-1 block w-full rounded border bg-white p-1 dark:bg-zinc-950"><option value="">Не выбрано</option>{field.options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select> : <input type={field.type ?? "text"} value={values[field.key] ?? ""} onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))} className="mt-1 block w-full rounded border bg-white p-1 dark:bg-zinc-950" />}</label>)}
      <div className="sm:col-span-2 flex gap-2"><button type="button" className="rounded border border-blue-500 bg-blue-600 px-3 py-1 text-sm text-white disabled:opacity-50" disabled={saving} onClick={() => void save()}>{saving ? "Сохранение…" : "Сохранить"}</button><button type="button" className="rounded border px-3 py-1 text-sm" disabled={saving} onClick={cancel}>Отмена</button></div>
    </div> : null}
    {voiding ? <div className="space-y-2"><p className="text-sm">Удаление аннулирует запись и сохраняется в истории.</p><label className="block text-sm">Причина удаления *<textarea value={reason} onChange={(event) => setReason(event.target.value)} className="mt-1 block w-full rounded border bg-white p-1 dark:bg-zinc-950" /></label><div className="flex gap-2"><button type="button" disabled={saving} className="rounded border border-red-500 px-3 py-1 text-sm text-red-700" onClick={() => void confirmVoid()}>Удалить</button><button type="button" disabled={saving} className="rounded border px-3 py-1 text-sm" onClick={cancel}>Отмена</button></div></div> : null}
  </div>;
}
