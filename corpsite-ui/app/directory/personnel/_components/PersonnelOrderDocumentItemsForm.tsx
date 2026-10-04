"use client";

import * as React from "react";

import { getEmployees } from "@/app/directory/employees/_lib/api.client";
import type { EmployeeDTO } from "@/app/directory/employees/_lib/types";
import {
  listPersonnelOrderDocumentItems,
  mapPersonnelOrdersApiError,
  patchPersonnelOrderDocumentItem,
  personnelOrderTypeLabel,
  type PersonnelOrderDetailResponse,
  type PersonnelOrderDocumentItem,
} from "../_lib/personnelOrdersApi.client";

const ITEM_TYPES = ["HIRE", "TRANSFER", "TERMINATION", "CONCURRENT_DUTY_START", "CONCURRENT_DUTY_END", "SUPPLEMENTARY_PAY", "RETURN_FROM_CHILDCARE_LEAVE", "LEAVE.ANNUAL.GRANT", "LEAVE.UNPAID.GRANT", "LEAVE.CHILDCARE.GRANT"];
const fieldClass = "mt-1 w-full rounded border border-zinc-300 bg-white p-2 text-sm dark:border-zinc-700 dark:bg-zinc-950";
const labelClass = "block text-sm font-medium text-zinc-800 dark:text-zinc-200";
const itemFields: (keyof PersonnelOrderDocumentItem)[] = ["item_type_code", "employee_id", "effective_date", "position_name", "org_unit_name", "specialty", "rate"];
type CorrectionReason = { code: string; text: string };
type ReasonErrors = { code?: boolean; text?: boolean };

function itemChanged(current: PersonnelOrderDocumentItem, saved: PersonnelOrderDocumentItem | undefined) {
  return !saved || itemFields.some((field) => (current[field] ?? "") !== (saved[field] ?? ""));
}

export default function PersonnelOrderDocumentItemsForm({ detail, onSaved, onDirtyChange }: {
  detail: PersonnelOrderDetailResponse;
  onSaved: () => Promise<void>;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const order = detail.order;
  const [items, setItems] = React.useState<PersonnelOrderDocumentItem[]>([]);
  const [revision, setRevision] = React.useState(order.document_revision ?? 1);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [messages, setMessages] = React.useState<Record<number, string>>({});
  const [matches, setMatches] = React.useState<Record<number, EmployeeDTO[]>>({});
  const [queries, setQueries] = React.useState<Record<number, string>>({});
  const [reasons, setReasons] = React.useState<Record<number, CorrectionReason>>({});
  const [reasonErrors, setReasonErrors] = React.useState<Record<number, ReasonErrors>>({});
  const [savingItemId, setSavingItemId] = React.useState<number | null>(null);
  const savedItems = React.useRef<Record<number, PersonnelOrderDocumentItem>>({});
  const itemsRef = React.useRef<PersonnelOrderDocumentItem[]>([]);
  const reasonCodeRefs = React.useRef<Record<number, HTMLInputElement | null>>({});
  const reasonTextRefs = React.useRef<Record<number, HTMLTextAreaElement | null>>({});
  const registered = ["REGISTERED", "SIGNED"].includes(order.status);

  const load = React.useCallback(async (preserveOtherDrafts = false, savedItemId?: number) => {
    const result = await listPersonnelOrderDocumentItems(order.order_id);
    const previousItems = itemsRef.current;
    const previousSaved = savedItems.current;
    savedItems.current = Object.fromEntries(result.items.map((item) => [item.item_id, item]));
    setItems(result.items.map((item) => {
      const previous = previousItems.find((entry) => entry.item_id === item.item_id);
      return preserveOtherDrafts && item.item_id !== savedItemId && previous && itemChanged(previous, previousSaved[item.item_id]) ? previous : item;
    }));
    setRevision(result.document_revision);
    setLoadError(null);
  }, [order.order_id]);
  React.useEffect(() => { void load().catch(() => setLoadError("Не удалось загрузить пункты приказа.")); }, [load]);
  React.useEffect(() => { itemsRef.current = items; }, [items]);

  const dirty = items.some((item) => itemChanged(item, savedItems.current[item.item_id]));
  React.useEffect(() => onDirtyChange?.(dirty), [dirty, onDirtyChange]);

  const change = (id: number, patch: Partial<PersonnelOrderDocumentItem>) => {
    setItems((current) => current.map((item) => item.item_id === id ? { ...item, ...patch } : item));
    setMessages((current) => { const next = { ...current }; delete next[id]; return next; });
  };
  const changeReason = (id: number, patch: Partial<CorrectionReason>) => {
    setReasons((current) => ({
      ...current,
      [id]: {
        code: patch.code ?? current[id]?.code ?? "",
        text: patch.text ?? current[id]?.text ?? "",
      },
    }));
    setReasonErrors((current) => ({ ...current, [id]: { ...current[id], ...(patch.code !== undefined ? { code: false } : {}), ...(patch.text !== undefined ? { text: false } : {}) } }));
  };
  async function search(id: number, query: string) {
    setQueries((current) => ({ ...current, [id]: query }));
    if (query.trim().length < 2) { setMatches((current) => ({ ...current, [id]: [] })); return; }
    const result = await getEmployees({ q: query.trim(), status: "active", limit: 10, offset: 0 });
    setMatches((current) => ({ ...current, [id]: result.items }));
  }
  async function save(item: PersonnelOrderDocumentItem) {
    if (savingItemId !== null) return;
    if (!itemChanged(item, savedItems.current[item.item_id])) { setMessages((current) => ({ ...current, [item.item_id]: "Изменений нет." })); return; }
    const reason = reasons[item.item_id] || { code: "", text: "" };
    if (registered && (!reason.code.trim() || !reason.text.trim())) {
      const errors = { code: !reason.code.trim(), text: !reason.text.trim() };
      setReasonErrors((current) => ({ ...current, [item.item_id]: errors }));
      setMessages((current) => ({ ...current, [item.item_id]: "Для сохранения заполните причину и пояснение." }));
      window.requestAnimationFrame(() => (errors.code ? reasonCodeRefs.current[item.item_id] : reasonTextRefs.current[item.item_id])?.focus());
      return;
    }
    setSavingItemId(item.item_id);
    setMessages((current) => { const next = { ...current }; delete next[item.item_id]; return next; });
    try {
      const result = await patchPersonnelOrderDocumentItem(order.order_id, item.item_id, {
        expected_document_revision: revision, item_type_code: item.item_type_code, employee_id: item.employee_id ?? null, effective_date: item.effective_date || null,
        document_subject_context: { position_name: item.position_name || null, org_unit_name: item.org_unit_name || null, specialty: item.specialty || null, rate: item.rate || null },
        reason_code: reason.code || null, reason_text: reason.text || null,
      });
      await onSaved(); await load(true, item.item_id);
      setReasons((current) => { const next = { ...current }; delete next[item.item_id]; return next; });
      setReasonErrors((current) => { const next = { ...current }; delete next[item.item_id]; return next; });
      setMessages((current) => ({ ...current, [item.item_id]: result.no_op ? "Изменений нет." : "Изменения сохранены." }));
    } catch (error) {
      const fallback = "Не удалось сохранить изменения.";
      const apiMessage = mapPersonnelOrdersApiError(error, fallback);
      setMessages((current) => ({ ...current, [item.item_id]: apiMessage === fallback ? fallback : `Не удалось сохранить изменения: ${apiMessage}` }));
    } finally { setSavingItemId(null); }
  }

  return <section data-testid="personnel-order-document-items" className="space-y-4">
    <h3 className="text-sm font-semibold">Пункты</h3><p className="text-xs text-zinc-500">Редактируется только документный контекст; кадровые данные и JSON не отображаются.</p>{loadError ? <p role="alert">{loadError}</p> : null}
    {items.map((item) => {
      const isDirty = itemChanged(item, savedItems.current[item.item_id]); const reason = reasons[item.item_id] || { code: "", text: "" }; const errors = reasonErrors[item.item_id] || {}; const saving = savingItemId === item.item_id;
      return <article key={item.item_id} className="space-y-4 rounded border border-zinc-200 p-4 dark:border-zinc-800"><div className="text-sm font-medium">Пункт {item.item_number}</div><div className="space-y-3">
        <label className={labelClass}>Тип пункта<select aria-label={`Тип пункта ${item.item_id}`} className={fieldClass} value={item.item_type_code} onChange={(event) => change(item.item_id, { item_type_code: event.target.value })}>{ITEM_TYPES.map((code) => <option key={code} value={code}>{personnelOrderTypeLabel(code)}</option>)}</select></label>
        <label className={labelClass}>Сотрудник<input aria-label={`Сотрудник ${item.item_id}`} className={fieldClass} value={queries[item.item_id] ?? item.employee_name ?? ""} placeholder="Начните вводить ФИО" onChange={(event) => void search(item.item_id, event.target.value)} /></label>
        {(matches[item.item_id] || []).map((employee) => <button key={employee.id} type="button" className="block w-full rounded border p-2 text-left text-sm" onClick={() => { change(item.item_id, { employee_id: Number(employee.id), employee_name: employee.fio || null, position_name: employee.position?.name || null, org_unit_name: employee.org_unit?.name || null }); setQueries((current) => ({ ...current, [item.item_id]: employee.fio || "" })); setMatches((current) => ({ ...current, [item.item_id]: [] })); }}>{employee.fio} · {employee.position?.name || "Должность не указана"} · {employee.org_unit?.name || "Отделение не указано"}</button>)}
        <label className={labelClass}>Должность в приказе<input aria-label={`Должность в приказе ${item.item_id}`} className={fieldClass} value={item.position_name || ""} onChange={(event) => change(item.item_id, { position_name: event.target.value || null })} /></label>
        <label className={labelClass}>Отделение в приказе<input aria-label={`Отделение в приказе ${item.item_id}`} className={fieldClass} value={item.org_unit_name || ""} onChange={(event) => change(item.item_id, { org_unit_name: event.target.value || null })} /></label>
        <label className={labelClass}>Специальность<input aria-label={`Специальность ${item.item_id}`} className={fieldClass} value={item.specialty || ""} onChange={(event) => change(item.item_id, { specialty: event.target.value || null })} /></label>
        <label className={labelClass}>Ставка в приказе<input aria-label={`Ставка в приказе ${item.item_id}`} className={fieldClass} value={item.rate || ""} onChange={(event) => change(item.item_id, { rate: event.target.value || null })} /></label>
        <label className={labelClass}>Дата действия<input aria-label={`Дата действия ${item.item_id}`} className={fieldClass} type="date" value={item.effective_date || ""} onChange={(event) => change(item.item_id, { effective_date: event.target.value || null })} /></label>
      </div>
      {registered && isDirty ? <div className="grid gap-3 rounded border border-amber-200 p-3 sm:grid-cols-2"><label className={labelClass}>Причина исправления<input ref={(node) => { reasonCodeRefs.current[item.item_id] = node; }} aria-label={`Причина исправления пункта ${item.item_id}`} aria-invalid={errors.code || undefined} className={`${fieldClass} ${errors.code ? "border-red-500" : ""}`} value={reason.code} onChange={(event) => changeReason(item.item_id, { code: event.target.value })} /></label><label className={labelClass}>Пояснение<textarea ref={(node) => { reasonTextRefs.current[item.item_id] = node; }} aria-label={`Пояснение исправления пункта ${item.item_id}`} aria-invalid={errors.text || undefined} className={`${fieldClass} ${errors.text ? "border-red-500" : ""}`} value={reason.text} onChange={(event) => changeReason(item.item_id, { text: event.target.value })} /></label></div> : null}
      <div className="flex flex-wrap items-center gap-3"><button type="button" disabled={savingItemId !== null} className="rounded bg-blue-600 px-3 py-2 text-sm text-white disabled:opacity-60" onClick={() => void save(item)}>{saving ? "Сохранение…" : "Сохранить изменения"}</button>{isDirty ? <span className="text-sm text-amber-700">Есть несохранённые изменения</span> : null}{messages[item.item_id] ? <span role="alert" className="text-sm">{messages[item.item_id]}</span> : null}</div>
      </article>;
    })}
  </section>;
}
