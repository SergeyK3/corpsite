"use client";
import { useState } from "react";
import { usePersonnelSectionLanguage } from "@/app/directory/personnel/_lib/personnelSectionLanguage";
import { PERSONNEL_ORDER_GROUPS, PERSONNEL_ORDER_TYPE_GROUP } from "@/app/directory/personnel/_lib/personnelOrderTypeGroups";
import { changePersonnelTemplateType, type PersonnelOrderTemplateDraft, type PersonnelOrderTemplateCatalogItem } from "../_lib/personnelOrderTemplatesApi.client";

export default function PersonnelTemplateTypeDialog({draft, catalog, onClose, onChanged}: {draft: PersonnelOrderTemplateDraft; catalog: PersonnelOrderTemplateCatalogItem[]; onClose: () => void; onChanged: (draft: PersonnelOrderTemplateDraft) => void}) {
  const {language} = usePersonnelSectionLanguage();
  const kk = language === "kk";
  const [target, setTarget] = useState(draft.item_type_code);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save() {
    setBusy(true); setError("");
    try { onChanged(await changePersonnelTemplateType(draft, target)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : (kk ? "Түрді өзгерту мүмкін болмады." : "Не удалось изменить вид.")); }
    finally { setBusy(false); }
  }
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"><section role="dialog" aria-modal="true" aria-label={kk ? "Үлгі түрін өзгерту" : "Изменить вид шаблона"} className="w-full max-w-xl space-y-4 rounded-xl bg-white p-6 dark:bg-zinc-900">
    <h3 className="font-semibold">{kk ? "Үлгі түрін өзгерту" : "Изменить вид шаблона"}</h3>
    <p>{kk ? draft.name_kk : draft.name_ru}</p>
    <p className="text-sm">{kk ? "Алдымен мәтіндегі өзгерістерді сақтаңыз. Сақталған мәтін өзгермейді. Жаңа түр өрістерді анықтайды; сәйкес келмейтін айнымалыларды жариялаудан бұрын түзету керек." : "Сначала сохраните изменения текста. Сохранённый текст останется прежним. Новый вид определяет поля; несовместимые переменные потребуется исправить до публикации."}</p>
    <label className="block text-sm">{kk ? "Бұйрық түрі" : "Вид приказа"}<select aria-label={kk ? "Бұйрық түрі" : "Вид приказа"} value={target} disabled={busy} onChange={e => setTarget(e.target.value)} className="mt-1 w-full rounded border p-2">
      {PERSONNEL_ORDER_GROUPS.map(group => <optgroup key={group.id} label={kk ? group.kk : group.ru}>{catalog.filter(item => PERSONNEL_ORDER_TYPE_GROUP[item.type_code as keyof typeof PERSONNEL_ORDER_TYPE_GROUP] === group.id).map(item => <option key={item.type_code} value={item.type_code}>{kk ? item.title_kk : item.title_ru}</option>)}</optgroup>)}
    </select></label>
    {error ? <p role="alert">{error}</p> : null}
    <div className="flex gap-3"><button type="button" disabled={busy || target === draft.item_type_code} onClick={() => void save()} className="rounded bg-blue-700 px-4 py-2 text-white">{kk ? "Түрді өзгерту" : "Изменить вид"}</button><button type="button" disabled={busy} onClick={onClose}>{kk ? "Бас тарту" : "Отмена"}</button></div>
  </section></div>;
}
