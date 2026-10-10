"use client";
import { useEffect, useRef, useState } from "react";
import { usePersonnelSectionLanguage } from "@/app/directory/personnel/_lib/personnelSectionLanguage";
import { removePersonnelTemplate, type PersonnelIndependentTemplate } from "../_lib/personnelOrderTemplatesApi.client";

export default function PersonnelTemplateRemoveDialog({ template, name: unsavedName, onClose, onRemoved }: {
  template?: PersonnelIndependentTemplate; name?: string; onClose: () => void; onRemoved: () => void;
}) {
  const { language } = usePersonnelSectionLanguage(); const kk = language === "kk";
  const name = template ? (kk ? template.name_kk || template.name_ru : template.name_ru || template.name_kk) : unsavedName || "Новый шаблон";
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  async function remove() {
    if (busy) return;
    setBusy(true); setError("");
    try {
      if (template) {
        const result = await removePersonnelTemplate(template);
        if (result.template_id !== template.template_id || !["DELETED", "ARCHIVED"].includes(result.action)) throw new Error("Deletion was not confirmed");
      }
      onRemoved();
    }
    catch { setError(kk ? "Үлгіні жою мүмкін болмады. Тізімді жаңартып, қайта көріңіз." : "Не удалось удалить шаблон. Обновите список и повторите попытку."); }
    finally { setBusy(false); }
  }
  return <dialog ref={dialog} aria-labelledby="template-remove-heading" data-testid="template-remove-dialog" onCancel={e => { e.preventDefault(); if (!busy) onClose(); }}
    className="m-auto w-[min(95vw,36rem)] rounded-xl border bg-white p-6 text-zinc-900 shadow-xl backdrop:bg-black/50 dark:bg-zinc-900 dark:text-zinc-50">
    <form className="space-y-4" onSubmit={e => { e.preventDefault(); void remove(); }}>
      <h4 id="template-remove-heading" className="text-lg font-semibold">{kk ? "Үлгіні жою" : "Удалить шаблон"}</h4>
      <p>{kk ? `«${name}»${template ? ` (ID ${template.template_id})` : ""} үлгісін және оның барлық сақталған нұсқаларын жою керек пе? Басқа үлгілер мен жасалған бұйрықтар сақталады` : `Удалить шаблон „${name}“${template ? ` (ID ${template.template_id})` : ""} и все его сохранённые версии? Другие шаблоны и созданные приказы сохранятся`}</p>
      {error ? <p role="alert" className="text-red-600">{error}</p> : null}
      <div className="flex gap-2">
        <button autoFocus type="button" disabled={busy} onClick={onClose} className="rounded border px-3 py-2">{kk ? "Бас тарту" : "Отмена"}</button>
        <button disabled={busy} type="submit" className="rounded bg-red-700 px-3 py-2 text-white disabled:opacity-50">{busy ? (kk ? "Орындалуда…" : "Удаление…") : (kk ? "Жою" : "Удалить")}</button>
      </div>
    </form>
  </dialog>;
}
