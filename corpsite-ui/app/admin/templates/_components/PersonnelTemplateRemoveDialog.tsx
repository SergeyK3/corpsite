"use client";
import { useEffect, useRef, useState } from "react";
import { usePersonnelSectionLanguage } from "@/app/directory/personnel/_lib/personnelSectionLanguage";
import { removePersonnelTemplate, type PersonnelIndependentTemplate } from "../_lib/personnelOrderTemplatesApi.client";

export default function PersonnelTemplateRemoveDialog({ template, onClose, onRemoved }: {
  template: PersonnelIndependentTemplate; onClose: () => void; onRemoved: () => void;
}) {
  const { language } = usePersonnelSectionLanguage(); const kk = language === "kk";
  const name = kk ? template.name_kk || template.name_ru : template.name_ru || template.name_kk;
  const [confirmation, setConfirmation] = useState(""); const [busy, setBusy] = useState(false);
  const [used, setUsed] = useState(false); const [error, setError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  async function remove(archive = false) {
    if (busy || confirmation.trim() !== name) return;
    setBusy(true); setError("");
    try { await removePersonnelTemplate(template, archive); onRemoved(); }
    catch (cause) {
      const code = (cause as {details?: {detail?: {code?: string}}})?.details?.detail?.code;
      if (code === "TEMPLATE_IN_USE") setUsed(true);
      else setError(kk ? "Үлгіні жою мүмкін болмады. Тізімді жаңартып, қайта көріңіз." : "Не удалось удалить шаблон. Обновите список и повторите попытку.");
    } finally { setBusy(false); }
  }
  return <dialog ref={dialog} aria-labelledby="template-remove-heading" onCancel={e => { e.preventDefault(); if (!busy) onClose(); }}
    className="m-auto w-[min(95vw,36rem)] rounded-xl border bg-white p-6 text-zinc-900 shadow-xl backdrop:bg-black/50 dark:bg-zinc-900 dark:text-zinc-50">
    <form className="space-y-4" onSubmit={e => { e.preventDefault(); void remove(used); }}>
      <h4 id="template-remove-heading" className="text-lg font-semibold">{kk ? "Үлгіні жою" : "Удалить шаблон"}: «{name}»</h4>
      <p>{used ? (kk ? "Үлгі қолданылған. Оны тарихын сақтай отырып мұрағаттауға болады; жаңа бұйрықтар үшін қолжетімсіз болады." : "Шаблон использован. Можно архивировать его с сохранением истории; для новых приказов он станет недоступен.")
        : (kk ? "Қолданылмаған дербес көшірмені жоюға болады. Бастапқы үлгі сақталады." : "Можно удалить неиспользуемую самостоятельную копию. Исходный шаблон сохранится.")}</p>
      <label className="block">{kk ? "Растау үшін үлгінің атауын енгізіңіз" : "Введите название шаблона для подтверждения"}
        <input autoFocus required disabled={busy} value={confirmation} onChange={e => setConfirmation(e.target.value)} className="mt-1 block w-full rounded border bg-transparent p-2" /></label>
      {error ? <p role="alert" className="text-red-600">{error}</p> : null}
      <div className="flex gap-2"><button disabled={busy || confirmation.trim() !== name} type="submit" className="rounded bg-red-700 px-3 py-2 text-white disabled:opacity-50">
        {busy ? (kk ? "Орындалуда…" : "Выполнение…") : used ? (kk ? "Тарихын сақтап мұрағаттау" : "Архивировать с сохранением истории") : (kk ? "Жою" : "Удалить")}</button>
        <button type="button" disabled={busy} onClick={onClose} className="rounded border px-3 py-2">{kk ? "Бас тарту" : "Отмена"}</button></div>
    </form>
  </dialog>;
}
