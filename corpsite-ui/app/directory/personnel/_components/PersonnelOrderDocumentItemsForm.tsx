"use client";

import * as React from "react";

import { getEmployees } from "@/app/directory/employees/_lib/api.client";
import type { EmployeeDTO } from "@/app/directory/employees/_lib/types";
import {
  listPersonnelOrderDocumentItems,
  patchPersonnelOrderDocumentItem,
  personnelOrderTypeLabel,
  type PersonnelOrderDetailResponse,
  type PersonnelOrderDocumentItem,
} from "../_lib/personnelOrdersApi.client";

const ITEM_TYPES = [
  "HIRE", "TRANSFER", "TERMINATION", "CONCURRENT_DUTY_START", "CONCURRENT_DUTY_END",
  "SUPPLEMENTARY_PAY", "RETURN_FROM_CHILDCARE_LEAVE", "LEAVE.ANNUAL.GRANT",
  "LEAVE.UNPAID.GRANT", "LEAVE.CHILDCARE.GRANT",
];
const fieldClass = "mt-1 w-full rounded border border-zinc-300 bg-white p-2 text-sm dark:border-zinc-700 dark:bg-zinc-950";
const labelClass = "block text-sm font-medium text-zinc-800 dark:text-zinc-200";

export default function PersonnelOrderDocumentItemsForm({ detail, onSaved }: {
  detail: PersonnelOrderDetailResponse;
  /** Parent reloads detail, review and effective/current editorial state. */
  onSaved: () => Promise<void>;
}) {
  const order = detail.order;
  const [items, setItems] = React.useState<PersonnelOrderDocumentItem[]>([]);
  const [revision, setRevision] = React.useState(order.document_revision ?? 1);
  const [message, setMessage] = React.useState<string | null>(null);
  const [matches, setMatches] = React.useState<Record<number, EmployeeDTO[]>>({});
  const [queries, setQueries] = React.useState<Record<number, string>>({});
  const registered = ["REGISTERED", "SIGNED"].includes(order.status);
  const [reasonCode, setReasonCode] = React.useState("");
  const [reasonText, setReasonText] = React.useState("");

  const load = React.useCallback(async () => {
    const result = await listPersonnelOrderDocumentItems(order.order_id);
    setItems(result.items);
    setRevision(result.document_revision);
  }, [order.order_id]);

  React.useEffect(() => {
    void load().catch(() => setMessage("Не удалось загрузить пункты приказа."));
  }, [load]);

  const change = (id: number, patch: Partial<PersonnelOrderDocumentItem>) => {
    setItems((current) => current.map((item) => item.item_id === id ? { ...item, ...patch } : item));
  };

  async function search(id: number, query: string) {
    setQueries((current) => ({ ...current, [id]: query }));
    if (query.trim().length < 2) {
      setMatches((current) => ({ ...current, [id]: [] }));
      return;
    }
    const result = await getEmployees({ q: query.trim(), status: "active", limit: 10, offset: 0 });
    setMatches((current) => ({ ...current, [id]: result.items }));
  }

  async function save(item: PersonnelOrderDocumentItem) {
    if (registered && (!reasonCode.trim() || !reasonText.trim())) {
      setMessage("Для зарегистрированного приказа укажите причину и пояснение.");
      return;
    }
    try {
      const result = await patchPersonnelOrderDocumentItem(order.order_id, item.item_id, {
        expected_document_revision: revision,
        item_type_code: item.item_type_code,
        employee_id: item.employee_id ?? null,
        effective_date: item.effective_date || null,
        document_subject_context: {
          position_name: item.position_name || null,
          org_unit_name: item.org_unit_name || null,
          specialty: item.specialty || null,
          rate: item.rate || null,
        },
        reason_code: reasonCode || null,
        reason_text: reasonText || null,
      });
      setMessage(result.no_op ? "Изменений нет." : "Изменения сохранены.");
      // The parent fetches the effective/current blocks used by Document and print.
      await onSaved();
      await load();
    } catch (error) {
      setMessage(String(error).includes("409")
        ? "Приказ был изменён другим пользователем. Обновите данные и повторите действие."
        : "Не удалось сохранить изменения.");
    }
  }

  return <section data-testid="personnel-order-document-items" className="space-y-4">
    <h3 className="text-sm font-semibold">Пункты</h3>
    <p className="text-xs text-zinc-500">Редактируется только документный контекст; кадровые данные и JSON не отображаются.</p>
    {registered ? <div className="grid gap-3 rounded border border-amber-200 p-3 sm:grid-cols-2">
      <label className={labelClass}>Причина исправления
        <input aria-label="Причина исправления пункта" className={fieldClass} value={reasonCode} onChange={(event) => setReasonCode(event.target.value)} />
      </label>
      <label className={labelClass}>Пояснение
        <textarea aria-label="Пояснение исправления пункта" className={fieldClass} value={reasonText} onChange={(event) => setReasonText(event.target.value)} />
      </label>
    </div> : null}
    {message ? <p role="alert">{message}</p> : null}
    {items.map((item) => <article key={item.item_id} className="space-y-4 rounded border border-zinc-200 p-4 dark:border-zinc-800">
      <div className="text-sm font-medium">Пункт {item.item_number}</div>
      <div className="space-y-3">
        <label className={labelClass}>Тип пункта
          <select aria-label={`Тип пункта ${item.item_id}`} className={fieldClass} value={item.item_type_code} onChange={(event) => change(item.item_id, { item_type_code: event.target.value })}>
            {ITEM_TYPES.map((code) => <option key={code} value={code}>{personnelOrderTypeLabel(code)}</option>)}
          </select>
        </label>
        <label className={labelClass}>Сотрудник
          <input aria-label={`Сотрудник ${item.item_id}`} className={fieldClass} value={queries[item.item_id] ?? item.employee_name ?? ""} placeholder="Начните вводить ФИО" onChange={(event) => void search(item.item_id, event.target.value)} />
        </label>
        {(matches[item.item_id] || []).map((employee) => <button key={employee.id} type="button" className="block w-full rounded border p-2 text-left text-sm" onClick={() => {
          change(item.item_id, { employee_id: Number(employee.id), employee_name: employee.fio || null, position_name: employee.position?.name || null, org_unit_name: employee.org_unit?.name || null });
          setQueries((current) => ({ ...current, [item.item_id]: employee.fio || "" }));
          setMatches((current) => ({ ...current, [item.item_id]: [] }));
        }}>{employee.fio} · {employee.position?.name || "Должность не указана"} · {employee.org_unit?.name || "Отделение не указано"}</button>)}
        <label className={labelClass}>Должность в приказе
          <input aria-label={`Должность в приказе ${item.item_id}`} className={fieldClass} value={item.position_name || ""} onChange={(event) => change(item.item_id, { position_name: event.target.value || null })} />
        </label>
        <label className={labelClass}>Отделение в приказе
          <input aria-label={`Отделение в приказе ${item.item_id}`} className={fieldClass} value={item.org_unit_name || ""} onChange={(event) => change(item.item_id, { org_unit_name: event.target.value || null })} />
        </label>
        <label className={labelClass}>Специальность
          <input aria-label={`Специальность ${item.item_id}`} className={fieldClass} value={item.specialty || ""} onChange={(event) => change(item.item_id, { specialty: event.target.value || null })} />
        </label>
        <label className={labelClass}>Ставка в приказе
          <input aria-label={`Ставка в приказе ${item.item_id}`} className={fieldClass} value={item.rate || ""} onChange={(event) => change(item.item_id, { rate: event.target.value || null })} />
        </label>
        <label className={labelClass}>Дата действия
          <input aria-label={`Дата действия ${item.item_id}`} className={fieldClass} type="date" value={item.effective_date || ""} onChange={(event) => change(item.item_id, { effective_date: event.target.value || null })} />
        </label>
      </div>
      <button type="button" className="w-full rounded bg-blue-600 px-3 py-2 text-sm text-white" onClick={() => void save(item)}>Сохранить изменения</button>
    </article>)}
  </section>;
}
