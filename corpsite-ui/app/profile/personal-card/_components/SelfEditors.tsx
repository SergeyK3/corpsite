"use client";

import { FormEvent, useEffect, useState } from "react";

import PersonnelDayDateField from "@/lib/PersonnelDayDateField";
import {
  displayForeignLanguageLevel,
  foreignLanguageLevelForEditor,
  FOREIGN_LANGUAGE_LEVELS,
  type ForeignLanguageLevel,
} from "../_lib/foreignLanguageDisplay";
import {
  addMyEducation,
  addMyExternalEmployment,
  getMyContacts,
  getMyForeignLanguages,
  saveMyContacts,
  saveMyForeignLanguages,
  supersedeMyExternalEmployment,
} from "../_lib/selfPersonalCardApi.client";

type EditorProps = { onSaved: () => Promise<void> };
type StringRecord = Record<string, string>;

const inputClassName =
  "mt-1 h-11 w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-base text-slate-900 shadow-sm outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100";
const selectClassName = inputClassName;

function apiErrorMessage(error: unknown, labels: Record<string, string>) {
  const candidate = error as { status?: number; message?: string; details?: { detail?: Array<{ loc?: unknown[]; msg?: string }> } };
  if (candidate?.status === 409) return "Данные изменились. Обновите карточку и повторите.";
  const issue = candidate?.details?.detail?.[0];
  const location = Array.isArray(issue?.loc) ? issue.loc[issue.loc.length - 1] : undefined;
  if (typeof location === "string" && labels[location] && issue?.msg) {
    return `Поле «${labels[location]}»: ${issue.msg.replace(/^Value error,\s*/i, "")}`;
  }
  return candidate?.message || "Не удалось сохранить изменения.";
}

function valuesEqual(left: StringRecord, right: StringRecord) {
  const keys = new Set([...Object.keys(left), ...Object.keys(right)]);
  return [...keys].every((key) => (left[key] ?? "") === (right[key] ?? ""));
}

function useDraft<T extends StringRecord>(initial: T) {
  const [saved, setSaved] = useState<T>(initial);
  const [values, setValues] = useState<T>(initial);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = !valuesEqual(values, saved);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  return {
    saved,
    values,
    editing,
    error,
    dirty,
    begin: () => { setError(null); setEditing(true); },
    change: (key: keyof T, value: string) => setValues((current) => ({ ...current, [key]: value })),
    replace: (next: T) => { setSaved(next); setValues(next); },
    cancel: () => {
      if (dirty && !window.confirm("Отменить несохранённые изменения?")) return;
      setValues(saved);
      setError(null);
      setEditing(false);
    },
    fail: (message: string) => setError(message),
    finish: () => { setSaved(values); setError(null); setEditing(false); },
  };
}

function EditorCard({ children, testId }: { children: React.ReactNode; testId: string }) {
  return <section data-testid={testId} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">{children}</section>;
}

function EditorActions({ editing, dirty, onEdit, onCancel }: {
  editing: boolean;
  dirty: boolean;
  onEdit: () => void;
  onCancel: () => void;
}) {
  if (!editing) {
    return <button type="button" className="rounded-md border border-blue-600 px-4 py-2 text-base font-medium text-blue-700 hover:bg-blue-50" onClick={onEdit}>Редактировать</button>;
  }
  return <>
    {dirty && <p role="alert" className="mb-4 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-base text-amber-950">Есть несохранённые изменения</p>}
    <div className="flex flex-wrap gap-3">
      <button type="submit" className="rounded-md bg-blue-600 px-4 py-2 text-base font-medium text-white hover:bg-blue-700">Сохранить</button>
      <button type="button" className="rounded-md border border-slate-400 px-4 py-2 text-base font-medium text-slate-800 hover:bg-slate-50" onClick={onCancel}>Отмена</button>
    </div>
  </>;
}

function TextField({ label, value, onChange, type = "text", required = false }: {
  label: string; value: string; onChange: (value: string) => void; type?: string; required?: boolean;
}) {
  return <label className="block text-base font-medium text-slate-800">{label}
    <input type={type} required={required} value={value} onChange={(event) => onChange(event.target.value)} className={inputClassName} />
  </label>;
}

export function ContactsEditor({ onSaved }: EditorProps) {
  const draft = useDraft({ mobile_phone: "", email: "", registration_address: "", residence_address: "" });
  const [version, setVersion] = useState<number | null>(null);
  const labels = { mobile_phone: "Мобильный телефон", email: "Email", registration_address: "Адрес регистрации", residence_address: "Адрес проживания" };

  const load = async () => {
    const response = await getMyContacts();
    const source = (response.canonical ?? response.fallback ?? {}) as Record<string, unknown>;
    const text = (key: string) => typeof source[key] === "string" ? source[key] : "";
    draft.replace({
      mobile_phone: text("mobile_phone"), email: text("email"),
      registration_address: text("registration_address"), residence_address: text("residence_address"),
    });
    setVersion(typeof source.version === "number" ? source.version : null);
  };
  useEffect(() => { void load(); }, []); // initial self-only fetch

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await saveMyContacts({ ...draft.values, expected_version: version });
      await onSaved();
      await load();
      draft.finish();
    } catch (error) { draft.fail(apiErrorMessage(error, labels)); }
  };
  return <EditorCard testId="self-contacts-editor">
    <h2 className="mb-4 text-xl font-semibold text-slate-900">Контакты</h2>
    <form onSubmit={submit} className="space-y-4">
      {draft.editing && <div className="grid gap-4 md:grid-cols-2">
        <TextField label="Мобильный телефон" value={draft.values.mobile_phone} onChange={(value) => draft.change("mobile_phone", value)} />
        <TextField label="Email" type="email" value={draft.values.email} onChange={(value) => draft.change("email", value)} />
        <TextField label="Адрес регистрации" value={draft.values.registration_address} onChange={(value) => draft.change("registration_address", value)} />
        <TextField label="Адрес проживания" value={draft.values.residence_address} onChange={(value) => draft.change("residence_address", value)} />
      </div>}
      {draft.error && <p role="alert" className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-red-900">{draft.error}</p>}
      <EditorActions editing={draft.editing} dirty={draft.dirty} onEdit={draft.begin} onCancel={draft.cancel} />
    </form>
  </EditorCard>;
}

const educationKinds = [["basic", "Основное"], ["internship", "Интернатура"], ["residency", "Резидентура"], ["masters", "Магистратура"], ["phd", "Докторантура"], ["other", "Другое"]];
const institutionTypes = [["university", "ВУЗ"], ["college", "Колледж"], ["other", "Другое"], ["unknown", "Не указано"]];

export function EducationEditor({ onSaved }: EditorProps) {
  const draft = useDraft({ education_kind: "basic", institution_type: "university", institution_name: "", specialty: "", qualification: "", started_at: "", completed_at: "", diploma_number: "", document_date: "" });
  const labels = { institution_name: "Учебное заведение", specialty: "Специальность", completed_at: "Дата окончания" };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await addMyEducation(draft.values);
      await onSaved();
      draft.finish();
    } catch (error) { draft.fail(apiErrorMessage(error, labels)); }
  };
  return <EditorCard testId="self-education-editor">
    <h2 className="mb-4 text-xl font-semibold text-slate-900">Образование</h2>
    <form onSubmit={submit} className="space-y-4">
      {draft.editing && <div className="grid gap-4 md:grid-cols-2">
        <label className="block text-base font-medium text-slate-800">Вид образования<select className={selectClassName} value={draft.values.education_kind} onChange={(e) => draft.change("education_kind", e.target.value)}>{educationKinds.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label className="block text-base font-medium text-slate-800">Тип учреждения<select className={selectClassName} value={draft.values.institution_type} onChange={(e) => draft.change("institution_type", e.target.value)}>{institutionTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <TextField required label="Учебное заведение" value={draft.values.institution_name} onChange={(value) => draft.change("institution_name", value)} />
        <TextField label="Специальность" value={draft.values.specialty} onChange={(value) => draft.change("specialty", value)} />
        <TextField label="Квалификация" value={draft.values.qualification} onChange={(value) => draft.change("qualification", value)} />
        <TextField label="Номер диплома" value={draft.values.diploma_number} onChange={(value) => draft.change("diploma_number", value)} />
        <PersonnelDayDateField label="Дата начала" value={draft.values.started_at} onChange={(value) => draft.change("started_at", value)} inputClassName={inputClassName} />
        <PersonnelDayDateField label="Дата окончания" value={draft.values.completed_at} onChange={(value) => draft.change("completed_at", value)} inputClassName={inputClassName} />
        <PersonnelDayDateField label="Дата документа" value={draft.values.document_date} onChange={(value) => draft.change("document_date", value)} inputClassName={inputClassName} />
      </div>}
      {draft.error && <p role="alert" className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-red-900">{draft.error}</p>}
      <EditorActions editing={draft.editing} dirty={draft.dirty} onEdit={draft.begin} onCancel={draft.cancel} />
    </form>
  </EditorCard>;
}

const languages = ["Казахский", "Русский", "Английский", "Немецкий", "Французский", "Китайский", "Турецкий", "Арабский", "Узбекский", "Кыргызский", "Корейский", "Испанский", "Другой"];
const levels = FOREIGN_LANGUAGE_LEVELS;

export function LanguagesEditor({ onSaved }: EditorProps) {
  const draft = useDraft<{ language: string; proficiency: ForeignLanguageLevel; other_language: string }>({ language: "", proficiency: levels[0], other_language: "" });
  const [items, setItems] = useState<Array<{ language: string; proficiency: string }>>([]);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const load = async () => {
    const response = await getMyForeignLanguages();
    const next = response.foreign_languages ?? [];
    setItems(next);
    setUpdatedAt(response.updated_at ?? null);
    return next;
  };
  useEffect(() => { void load(); }, []);
  const begin = async (index: number | null) => {
    const current = await load();
    const item = index === null ? undefined : current[index];
    const known = item && languages.includes(item.language) ? item.language : item ? "Другой" : "";
    draft.replace({ language: known, proficiency: foreignLanguageLevelForEditor(item?.proficiency), other_language: known === "Другой" ? item?.language ?? "" : "" });
    setEditingIndex(index);
    draft.begin();
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const language = draft.values.language === "Другой" ? draft.values.other_language.trim() : draft.values.language;
    if (!language) { draft.fail("Укажите язык."); return; }
    if (items.some((item, index) => index !== editingIndex && item.language.toLocaleLowerCase() === language.toLocaleLowerCase())) { draft.fail("Этот язык уже добавлен."); return; }
    try {
      const foreign_languages = editingIndex === null
        ? [...items, { language, proficiency: draft.values.proficiency }]
        : items.map((item, index) => index === editingIndex ? { language, proficiency: draft.values.proficiency } : item);
      const saved = await saveMyForeignLanguages({ foreign_languages, expected_updated_at: updatedAt }) as { updated_at?: string | null };
      setUpdatedAt(saved.updated_at ?? null);
      await onSaved();
      await load();
      draft.finish();
    } catch (error) { draft.fail(apiErrorMessage(error, { language: "Язык", proficiency: "Уровень владения" })); }
  };
  return <EditorCard testId="self-languages-editor">
    <h2 className="mb-4 text-xl font-semibold text-slate-900">Иностранные языки</h2>
    <form onSubmit={submit} className="space-y-4">
      {!draft.editing && <div className="space-y-3">
        {items.map((item, index) => <div key={`${item.language}-${index}`} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 p-3"><span>{item.language} — {displayForeignLanguageLevel(item.proficiency)}</span><button type="button" className="rounded-md border border-blue-600 px-3 py-1.5 text-blue-700 hover:bg-blue-50" onClick={() => { void begin(index); }}>Редактировать</button></div>)}
        <button type="button" className="rounded-md border border-blue-600 px-4 py-2 text-base font-medium text-blue-700 hover:bg-blue-50" onClick={() => { void begin(null); }}>Добавить язык</button>
      </div>}
      {draft.editing && <div className="grid gap-4 md:grid-cols-2">
        <label className="block text-base font-medium text-slate-800">Язык<select required className={selectClassName} value={draft.values.language} onChange={(e) => draft.change("language", e.target.value)}><option value="">Выберите язык</option>{languages.map((language) => <option key={language} value={language}>{language}</option>)}</select></label>
        <label className="block text-base font-medium text-slate-800">Уровень владения<select className={selectClassName} value={draft.values.proficiency} onChange={(e) => draft.change("proficiency", e.target.value)}>{levels.map((level) => <option key={level} value={level}>{level}</option>)}</select></label>
        {draft.values.language === "Другой" && <TextField required label="Укажите язык" value={draft.values.other_language} onChange={(value) => draft.change("other_language", value)} />}
      </div>}
      {draft.error && <p role="alert" className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-red-900">{draft.error}</p>}
      {draft.editing && <EditorActions editing={draft.editing} dirty={draft.dirty} onEdit={() => { void begin(null); }} onCancel={draft.cancel} />}
    </form>
  </EditorCard>;
}

type EmploymentDraft = {
  commandId: string; recordId?: number; expectedUpdatedAt?: string; record_kind: string; employer_name: string; position_title: string; started_at: string; ended_at: string;
  termination_reason: string; other_termination_reason: string;
};

export type EmploymentRecordForEdit = {
  record_id: number; updated_at: string; record_kind: string; employer_name: string | null; position_title: string | null;
  started_at: string | null; ended_at: string | null; termination_reason: string | null;
};

const terminationReasons = [
  ["По собственному желанию", "По собственному желанию"],
  ["Перевод", "Перевод"],
  ["Переезд в другой регион", "Переезд в другой регион"],
  ["other", "Другое"],
] as const;

function newEmploymentDraft(record?: EmploymentRecordForEdit): EmploymentDraft {
  const key = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
  const knownReason = terminationReasons.some(([value]) => value === record?.termination_reason) ? record?.termination_reason ?? "" : record?.termination_reason ? "other" : "";
  return { commandId: `self-employment-${key}`, recordId: record?.record_id, expectedUpdatedAt: record?.updated_at, record_kind: record?.record_kind ?? "episode", employer_name: record?.employer_name ?? "", position_title: record?.position_title ?? "", started_at: record?.started_at ?? "", ended_at: record?.ended_at ?? "", termination_reason: knownReason, other_termination_reason: knownReason === "other" ? record?.termination_reason ?? "" : "" };
}

export function EmploymentEditor({ onSaved, editRecord, onEditClosed }: EditorProps & { editRecord?: EmploymentRecordForEdit | null; onEditClosed?: () => void }) {
  const [saved, setSaved] = useState<EmploymentDraft | null>(null);
  const [draft, setDraft] = useState<EmploymentDraft | null>(null);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = ""; } };
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [dirty]);

  useEffect(() => {
    if (!editRecord) return;
    const next = newEmploymentDraft(editRecord);
    setSaved(next); setDraft(next); setError(null); setEditing(true);
  }, [editRecord?.record_id, editRecord?.updated_at]);

  const change = (field: keyof EmploymentDraft, value: string) => setDraft((current) => current ? { ...current, [field]: value } : current);
  const begin = () => { const next = newEmploymentDraft(); setError(null); setSaved(next); setDraft(next); setEditing(true); };
  const cancel = () => {
    if (dirty && !window.confirm("Отменить несохранённые изменения?")) return;
    setDraft(saved); setError(null); setEditing(false); onEditClosed?.();
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!draft) return;
    if (!draft.employer_name.trim() || !draft.position_title.trim()) { setError("Заполните организацию и должность."); return; }
    if (draft.termination_reason === "other" && !draft.other_termination_reason.trim()) { setError("Укажите другую причину увольнения."); return; }
    if (draft.started_at && draft.ended_at && draft.started_at > draft.ended_at) { setError("Дата окончания не может быть раньше даты начала."); return; }
    try {
      const termination_reason = draft.termination_reason === "other" ? draft.other_termination_reason.trim() : draft.termination_reason || null;
      const replacement = { record_kind: draft.record_kind, employer_name: draft.employer_name, position_title: draft.position_title, started_at: draft.started_at || null, ended_at: draft.ended_at || null, termination_reason };
      if (draft.recordId && draft.expectedUpdatedAt) {
        await supersedeMyExternalEmployment(draft.recordId, { expected_updated_at: draft.expectedUpdatedAt, replacement }, draft.commandId);
      } else {
        await addMyExternalEmployment(replacement, draft.commandId);
      }
      await onSaved();
      setSaved(draft); setError(null); setEditing(false); onEditClosed?.();
    } catch (reason) { setError(apiErrorMessage(reason, { employer_name: "Организация", position_title: "Должность", started_at: "Дата начала", ended_at: "Дата окончания" })); }
  };
  return <EditorCard testId="self-employment-editor">
    {!editing ? <button type="button" className="rounded-md border border-blue-600 px-4 py-2 text-base font-medium text-blue-700 hover:bg-blue-50" onClick={begin}>Добавить место работы</button> : <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <TextField required label="Организация" value={draft?.employer_name ?? ""} onChange={(value) => change("employer_name", value)} />
        <TextField required label="Должность" value={draft?.position_title ?? ""} onChange={(value) => change("position_title", value)} />
        <label className="block text-base font-medium text-slate-800">Причина увольнения<select className={selectClassName} value={draft?.termination_reason ?? ""} onChange={(event) => change("termination_reason", event.target.value)}><option value="">Не указана</option>{terminationReasons.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        {draft?.termination_reason === "other" && <TextField required label="Другая причина увольнения" value={draft.other_termination_reason} onChange={(value) => change("other_termination_reason", value)} />}
        <PersonnelDayDateField label="Дата начала" value={draft?.started_at ?? ""} onChange={(value) => change("started_at", value)} inputClassName={inputClassName} />
        <PersonnelDayDateField label="Дата окончания" value={draft?.ended_at ?? ""} onChange={(value) => change("ended_at", value)} inputClassName={inputClassName} />
      </div>
      {error && <p role="alert" className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-red-900">{error}</p>}
      <EditorActions editing={editing} dirty={dirty} onEdit={begin} onCancel={cancel} />
    </form>}
  </EditorCard>;
}
