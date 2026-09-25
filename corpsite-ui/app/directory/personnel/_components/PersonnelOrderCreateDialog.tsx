"use client";

import * as React from "react";
import { PERSONNEL_ORDER_CREATE_TYPE_OPTIONS, createManualPersonnelOrderDraft, mapPersonnelOrdersApiError, previewPersonnelOrderHeaderDuplicate, type PersonnelOrderManualDraftCreateResult } from "../_lib/personnelOrdersApi.client";

type Props = { open: boolean; onClose: () => void; onCreated: (result: PersonnelOrderManualDraftCreateResult) => void };

export default function PersonnelOrderCreateDialog({ open, onClose, onCreated }: Props) {
  const [number, setNumber] = React.useState(""); const [orderDate, setOrderDate] = React.useState(""); const [title, setTitle] = React.useState(""); const [locale, setLocale] = React.useState<"kk" | "ru">("kk");
  const [itemType, setItemType] = React.useState("HIRE"); const [employeeId, setEmployeeId] = React.useState(""); const [effectiveDate, setEffectiveDate] = React.useState(""); const [submitting, setSubmitting] = React.useState(false); const [error, setError] = React.useState<string | null>(null);
  React.useEffect(() => { if (open) { setNumber(""); setOrderDate(""); setTitle(""); setLocale("kk"); setItemType("HIRE"); setEmployeeId(""); setEffectiveDate(""); setError(null); } }, [open]);
  if (!open) return null;
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setSubmitting(true); setError(null);
    try {
      const duplicate = await previewPersonnelOrderHeaderDuplicate({ order_number: number, order_date: orderDate });
      if (duplicate.blocking) { setError("Найден приказ с таким же номером и датой."); return; }
      if (duplicate.warnings.length && !window.confirm("Есть приказ с тем же номером и другой датой. Продолжить?")) return;
      const result = await createManualPersonnelOrderDraft({ order_number: number, order_date: orderDate, source_title: title, source_title_locale: locale, item_type_code: itemType, employee_id: Number(employeeId), effective_date: effectiveDate });
      onCreated(result); onClose();
    } catch (err) { setError(mapPersonnelOrdersApiError(err, "Не удалось создать приказ.")); } finally { setSubmitting(false); }
  }
  return <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" data-testid="personnel-order-create-dialog"><button type="button" aria-label="Закрыть" className="absolute inset-0 bg-black/40" onClick={onClose} />
    <div className="relative w-full max-w-md rounded-xl border border-zinc-200 bg-white p-5 shadow-xl"><h2 className="text-lg font-semibold">Создать приказ</h2><p className="mt-1 text-sm text-zinc-500">Ручной черновик с одним пунктом; кадровые последствия не создаются.</p>
      <form className="mt-4 space-y-3" onSubmit={submit}>
        <label className="block text-sm">Номер приказа<input aria-label="Номер приказа" required value={number} onChange={(e) => setNumber(e.target.value)} className="mt-1 w-full rounded border p-2" /></label><label className="block text-sm">Дата приказа<input aria-label="Дата приказа" type="date" required value={orderDate} onChange={(e) => setOrderDate(e.target.value)} className="mt-1 w-full rounded border p-2" /></label>
        <label className="block text-sm">Исходное название<textarea aria-label="Исходное название" required value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1 w-full rounded border p-2" /></label><label className="block text-sm">Язык исходного названия<select aria-label="Язык исходного названия" value={locale} onChange={(e) => setLocale(e.target.value as "kk" | "ru")} className="mt-1 w-full rounded border p-2"><option value="kk">Қазақша</option><option value="ru">Русский</option></select></label>
        <label className="block text-sm">Тип пункта<select aria-label="Тип пункта" value={itemType} onChange={(e) => setItemType(e.target.value)} className="mt-1 w-full rounded border p-2">{PERSONNEL_ORDER_CREATE_TYPE_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label><label className="block text-sm">Сотрудник<input aria-label="Сотрудник" type="number" min="1" required value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} className="mt-1 w-full rounded border p-2" /></label><label className="block text-sm">Дата действия<input aria-label="Дата действия" type="date" required value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} className="mt-1 w-full rounded border p-2" /></label>
        {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}<div className="flex justify-end gap-2"><button type="button" onClick={onClose} className="rounded border px-3 py-2 text-sm">Отмена</button><button type="submit" disabled={submitting} className="rounded bg-blue-600 px-3 py-2 text-sm text-white">{submitting ? "Создание…" : "Создать приказ"}</button></div>
      </form></div></div>;
}
