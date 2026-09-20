"use client";

import * as React from "react";
import { savePprForeignLanguages } from "../_lib/pprQueryApi.client";

type Item = { language: string; proficiency: string };
const LANGUAGES = ["Казахский", "Русский", "Английский", "Немецкий", "Французский", "Китайский", "Турецкий", "Арабский", "Узбекский", "Кыргызский", "Корейский", "Испанский"];
const PROFICIENCIES = ["Со словарём", "Читает и может объясняться", "Владеет свободно"];
const commandId = () => globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
const selectValue = (language: string) => LANGUAGES.includes(language) ? language : "Другой";

export default function PprForeignLanguagesEditor({ personId, items, version, onSaved }: { personId: number; items: Item[]; version: string; onSaved: () => void }) {
  const [editing, setEditing] = React.useState(false); const [rows, setRows] = React.useState<Item[]>(items); const [saving, setSaving] = React.useState(false); const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => { const warn = (event: BeforeUnloadEvent) => { if (editing) event.preventDefault(); }; window.addEventListener("beforeunload", warn); return () => window.removeEventListener("beforeunload", warn); }, [editing]);
  const change = (index: number, patch: Partial<Item>) => setRows((current) => current.map((row, n) => n === index ? { ...row, ...patch } : row));
  const cancel = () => { setRows(items); setEditing(false); setError(null); };
  const save = async () => { const normalized = rows.map((row) => ({ language: row.language.trim(), proficiency: row.proficiency.trim() })); if (normalized.some((row) => !row.language || !row.proficiency)) { setError("Укажите язык и уровень владения."); return; } if (new Set(normalized.map((row) => row.language.toLocaleLowerCase())).size !== normalized.length) { setError("Одинаковый язык нельзя добавить дважды."); return; } setSaving(true); setError(null); try { await savePprForeignLanguages(personId, { command_id: commandId(), expected_updated_at: version || null, foreign_languages: normalized }); setEditing(false); onSaved(); } catch (caught) { const message = caught instanceof Error ? caught.message : "Не удалось сохранить языки."; setError(/409|conflict/i.test(message) ? "Данные изменены другим пользователем. Обновите карточку." : message); } finally { setSaving(false); } };
  if (!editing) return <button type="button" className="rounded border px-3 py-1 text-sm" onClick={() => setEditing(true)}>Редактировать</button>;
  return <div className="mt-3 space-y-3 rounded-lg border border-blue-200 bg-blue-50/50 p-3 dark:border-blue-900 dark:bg-blue-950/20" data-testid="ppr-foreign-languages-editor">
    {rows.map((row, index) => { const other = selectValue(row.language) === "Другой"; return <div key={index} className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
      <label className="text-sm">Язык<select aria-label={`Язык ${index + 1}`} value={selectValue(row.language)} onChange={(event) => change(index, { language: event.target.value === "Другой" ? (other ? row.language : "") : event.target.value })} className="mt-1 block w-full rounded border bg-white p-1 dark:bg-zinc-950"><option value="">Выберите язык</option>{LANGUAGES.map((language) => <option key={language} value={language}>{language}</option>)}<option value="Другой">Другой</option></select></label>
      <label className="text-sm">Уровень владения<select aria-label={`Уровень владения ${index + 1}`} value={row.proficiency} onChange={(event) => change(index, { proficiency: event.target.value })} className="mt-1 block w-full rounded border bg-white p-1 dark:bg-zinc-950"><option value="">Выберите уровень</option>{PROFICIENCIES.map((level) => <option key={level} value={level}>{level}</option>)}</select></label>
      <button type="button" className="self-end rounded border border-red-300 px-2 py-1 text-sm text-red-700" onClick={() => setRows((current) => current.filter((_, n) => n !== index))}>Удалить</button>
      {other ? <label className="text-sm sm:col-span-2">Укажите язык *<input aria-label={`Укажите язык ${index + 1}`} value={row.language} onChange={(event) => change(index, { language: event.target.value })} className="mt-1 block w-full rounded border bg-white p-1 dark:bg-zinc-950" /></label> : null}
    </div>; })}
    <button type="button" className="rounded border px-3 py-1 text-sm" onClick={() => setRows((current) => [...current, { language: "", proficiency: "" }])}>Добавить язык</button>
    <div className="flex gap-2"><button type="button" disabled={saving} className="rounded border border-blue-500 bg-blue-600 px-3 py-1 text-sm text-white disabled:opacity-50" onClick={() => void save()}>{saving ? "Сохранение…" : "Сохранить"}</button><button type="button" disabled={saving} className="rounded border px-3 py-1 text-sm" onClick={cancel}>Отмена</button></div>
    {error ? <p role="alert" className="text-sm text-red-700 dark:text-red-300">{error}</p> : null}
  </div>;
}
