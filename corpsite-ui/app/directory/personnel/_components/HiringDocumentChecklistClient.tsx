"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";

import {
  getHiringDocumentChecklist,
  updateHiringDocumentChecklist,
  type HiringDocumentChecklist,
  type HiringDocumentChecklistUpdate,
} from "../_lib/hiringDocumentChecklistApi.client";

const PAGE_TITLE = "Перечень документов при приеме на работу";

function toUpdate(value: HiringDocumentChecklist): HiringDocumentChecklistUpdate {
  const { can_edit: _canEdit, ...update } = value;
  return update;
}

export default function HiringDocumentChecklistClient() {
  const searchParams = useSearchParams();
  const [checklist, setChecklist] = React.useState<HiringDocumentChecklist | null>(null);
  const [draft, setDraft] = React.useState<HiringDocumentChecklistUpdate | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);
  const editRequested = searchParams.get("edit") === "1";

  React.useEffect(() => {
    void getHiringDocumentChecklist()
      .then((value) => {
        setChecklist(value);
        setDraft(toUpdate(value));
      })
      .catch(() => setError("Не удалось загрузить перечень документов."));
  }, []);

  if (error) return <main className="p-6 text-red-700">{error}</main>;
  if (!checklist || !draft) return <main className="p-6 text-zinc-500">Загрузка…</main>;

  const editing = editRequested && checklist.can_edit;
  const displayed = editing ? draft : toUpdate(checklist);
  const setItem = (index: number, value: string) =>
    setDraft((current) => current ? { ...current, items: current.items.map((item, i) => i === index ? value : item) } : current);
  const moveItem = (index: number, shift: number) => setDraft((current) => {
    if (!current || index + shift < 0 || index + shift >= current.items.length) return current;
    const items = [...current.items];
    [items[index], items[index + shift]] = [items[index + shift], items[index]];
    return { ...current, items };
  });
  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const saved = await updateHiringDocumentChecklist(draft);
      setChecklist(saved);
      setDraft(toUpdate(saved));
      window.history.replaceState(null, "", "/directory/personnel/hiring-document-checklist");
    } catch {
      setError("Не удалось сохранить шаблон.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="hiring-document-checklist-print mx-auto max-w-3xl p-6 text-zinc-900 print:max-w-none print:p-0" data-testid="hiring-document-checklist">
      <div className="mb-6 flex justify-end gap-2 print:hidden">
        {editing ? (
          <>
            <button type="button" onClick={() => { setDraft(toUpdate(checklist)); window.history.back(); }} className="rounded-lg border border-zinc-300 px-3 py-2 text-sm">Отменить</button>
            <button type="button" disabled={saving} onClick={() => void save()} className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">{saving ? "Сохранение…" : "Сохранить"}</button>
          </>
        ) : <>
          {checklist.can_edit ? <a href="?edit=1" className="rounded-lg border border-zinc-300 px-3 py-2 text-sm">Редактировать шаблон</a> : null}
          <button type="button" onClick={() => window.print()} className="rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white">Распечатать</button>
          <button type="button" onClick={() => window.close()} className="rounded-lg border border-zinc-300 px-3 py-2 text-sm">Закрыть</button>
        </>}
      </div>

      {editing ? <input aria-label="Заголовок" value={displayed.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} className="mb-6 w-full border-b border-zinc-400 text-2xl font-bold" /> : <h1 className="mb-6 text-2xl font-bold">{PAGE_TITLE}</h1>}
      <ol className="space-y-3">
        {displayed.items.map((item, index) => <li key={index} className="flex gap-3"><span className="mt-1 h-4 w-4 shrink-0 border border-zinc-900" />
          {editing ? <div className="flex flex-1 gap-2"><textarea aria-label={`Пункт ${index + 1}`} value={item} onChange={(e) => setItem(index, e.target.value)} className="min-h-16 flex-1 rounded border border-zinc-300 p-2" /><div className="flex flex-col gap-1"><button type="button" onClick={() => moveItem(index, -1)} disabled={index === 0}>↑</button><button type="button" onClick={() => moveItem(index, 1)} disabled={index === displayed.items.length - 1}>↓</button><button type="button" onClick={() => setDraft({ ...draft, items: draft.items.filter((_, i) => i !== index) })} disabled={displayed.items.length === 1}>×</button></div></div> : <span>{item}</span>}
        </li>)}
      </ol>
      {editing ? <button type="button" onClick={() => setDraft({ ...draft, items: [...draft.items, ""] })} className="mt-4 rounded border border-zinc-300 px-3 py-2 text-sm">Добавить пункт</button> : null}
      <section className="mt-8"><h2 className="font-semibold">Примечание</h2>{editing ? <textarea aria-label="Примечание" value={displayed.note} onChange={(e) => setDraft({ ...draft, note: e.target.value })} className="mt-2 min-h-24 w-full rounded border border-zinc-300 p-2" /> : <p className="mt-2">{displayed.note}</p>}</section>
      {editing ? <section className="mt-6 flex flex-wrap items-center gap-3"><label className="flex items-center gap-2"><input type="checkbox" checked={draft.show_additional_notes} onChange={(e) => setDraft({ ...draft, show_additional_notes: e.target.checked })} />Дополнительные строки</label><input aria-label="Количество строк" type="number" min="1" max="10" value={draft.additional_notes_lines} onChange={(e) => setDraft({ ...draft, additional_notes_lines: Number(e.target.value) })} className="w-20 rounded border border-zinc-300 p-1" /></section> : null}
      {displayed.show_additional_notes ? <section className="mt-8"><h2 className="font-semibold">Дополнительные документы и отметки</h2>{Array.from({ length: displayed.additional_notes_lines }, (_, i) => <div key={i} className="mt-5 border-b border-zinc-500" />)}</section> : null}
    </main>
  );
}
