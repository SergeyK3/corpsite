"use client";

import * as React from "react";
import { createPortal } from "react-dom";

import {
  formatPersonnelOrderDate,
  formatPersonnelOrderDateTime,
  formatPersonnelOrderNumber,
  getPersonnelOrder,
  getPersonnelOrderEditorial,
  getPersonnelOrderDocumentReview,
  confirmPersonnelOrderDocumentReview,
  reopenPersonnelOrderDocumentReview,
  previewPersonnelOrderHeaderDuplicate,
  patchPersonnelOrderDocumentHeader,
  listPersonnelOrderDocumentItems,
  patchPersonnelOrderDocumentItem,
  recordPersonnelOrderAcknowledgement,
  clearPersonnelOrderAcknowledgement,
  isWritablePersonnelOrder,
  isPersonnelOrderApplied,
  mapPersonnelOrdersApiError,
  personnelOrderSourceModeLabel,
  type PersonnelOrderDetailResponse,
  type PersonnelOrderEditorialState,
  type PersonnelOrderLinkedEvent,
  type PersonnelOrderDocumentReview,
  type PersonnelOrderDocumentItem,
} from "../_lib/personnelOrdersApi.client";
import {
  hasPersonnelOrderSignatory,
  mergePersonnelOrderRequisitesForPreview,
  resolvePersonnelOrderSignatoryDisplay,
  type PersonnelOrderRequisitesSnapshot,
} from "../_lib/personnelOrderDocumentRequisites";
import {
  normalizePersonnelOrderSignatoryRole,
  personnelOrderSignatoryRoleLabel,
} from "../_lib/personnelOrderSignatoryRole";
import PersonnelOrderAppliedBadge from "./PersonnelOrderAppliedBadge";
import PersonnelOrderArchivedBadge from "./PersonnelOrderArchivedBadge";
import PersonnelOrderEditorialTextEditor from "./PersonnelOrderEditorialTextEditor";
import PersonnelOrderHeaderEditor from "./PersonnelOrderHeaderEditor";
import PersonnelOrderItemEditor from "./PersonnelOrderItemEditor";
import PersonnelOrderLifecycleActions from "./PersonnelOrderLifecycleActions";
import PersonnelOrderStatusBadge from "./PersonnelOrderStatusBadge";
import PersonnelOrderTypeBadge from "./PersonnelOrderTypeBadge";
import PersonnelOrderDocumentView, {
  personnelOrderDocumentAvailable,
  type PersonnelOrderDocumentLanguage,
} from "./PersonnelOrderDocumentView";
import PersonnelOrderPrintLanguageDialog, {
  type PersonnelOrderPrintDialogAction,
} from "./print/PersonnelOrderPrintLanguageDialog";
import type { PersonnelOrderPrintLanguage } from "../_lib/personnelOrderPrintLanguage";
import { openPersonnelOrderPdf } from "../_lib/personnelOrderPdfOpen.client";
import {
  PERSONNEL_ORDER_PRINT_POPUP_BLOCKED_MESSAGE,
  openPersonnelOrderPrintPreview,
} from "../_lib/personnelOrderPrintPreview.client";

type Props = {
  orderId: number | null;
  open: boolean;
  onClose: () => void;
  onChanged?: (detail: PersonnelOrderDetailResponse) => void;
  hirePersonId?: number | null;
};

function PersonnelOrderAcknowledgements({ detail, onChanged }: { detail: PersonnelOrderDetailResponse; onChanged: (next: PersonnelOrderDetailResponse) => void }) {
  const subjects = Array.from(new Map((detail.items || [])
    .filter((item) => item.item_status === "ACTIVE" && item.employee_id != null)
    .map((item) => [item.employee_id!, item])).values());
  const [dates, setDates] = React.useState<Record<number, string>>({});
  if (!subjects.length) return null;
  async function reload() { onChanged(await getPersonnelOrder(detail.order.order_id)); }
  return <section data-testid="personnel-order-acknowledgements">
    <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Ознакомление с приказом</h3>
    <div className="space-y-3">
      {subjects.map((item) => {
        const current = (detail.acknowledgements || []).find((entry) => entry.employee_id === item.employee_id);
        const value = dates[item.employee_id!] ?? (current?.event_type === "CLEARED" ? "" : current?.acknowledged_on || "");
        return <div key={item.employee_id} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <div className="text-sm font-medium">{item.employee_name || "Требуется кадровая проверка"}</div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <input aria-label={`Дата ознакомления ${item.employee_id}`} type="date" value={value}
              onChange={(event) => setDates((old) => ({ ...old, [item.employee_id!]: event.target.value }))}
              className="rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700" />
            <button type="button" disabled={!value} className="rounded bg-blue-600 px-2 py-1 text-sm text-white disabled:opacity-50"
              onClick={async () => { if (current && current.acknowledged_on && current.acknowledged_on !== value && !window.confirm("Исправить дату ознакомления?")) return; await recordPersonnelOrderAcknowledgement(detail.order.order_id, item.employee_id!, value); await reload(); }}>
              {current?.acknowledged_on ? "Исправить" : "Зарегистрировать"}
            </button>
            {current?.acknowledged_on ? <button type="button" className="rounded border border-red-300 px-2 py-1 text-sm text-red-700"
              onClick={async () => { if (!window.confirm("Очистить ошибочную дату ознакомления?")) return; await clearPersonnelOrderAcknowledgement(detail.order.order_id, item.employee_id!); await reload(); }}>Очистить</button> : null}
          </div>
        </div>;
      })}
    </div>
  </section>;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-zinc-800 dark:text-zinc-200">{value}</dd>
    </div>
  );
}

function PersonnelOrderDocumentHeaderForm({ detail, onSaved }: { detail: PersonnelOrderDetailResponse; onSaved: () => Promise<void> }) {
  const order = detail.order;
  const [number, setNumber] = React.useState(order.order_number || "");
  const [orderDate, setOrderDate] = React.useState(order.order_date || "");
  const [title, setTitle] = React.useState(order.source_title || "");
  const [locale, setLocale] = React.useState(order.source_title_locale || "unknown");
  const [reasonCode, setReasonCode] = React.useState(""); const [reasonText, setReasonText] = React.useState("");
  const [message, setMessage] = React.useState<string | null>(null); const registered = ["REGISTERED", "SIGNED"].includes(order.status);
  async function save() {
    if (registered && (!reasonCode.trim() || !reasonText.trim())) { setMessage("Для зарегистрированного приказа укажите причину и пояснение."); return; }
    try {
      const duplicate = await previewPersonnelOrderHeaderDuplicate({ order_id: order.order_id, order_number: number, order_date: orderDate || null });
      if (duplicate.blocking) { setMessage("Найден дублирующий номер приказа и дата."); return; }
      if (duplicate.warnings.length && !window.confirm("Есть приказ с тем же номером и другой датой. Продолжить?")) return;
      await patchPersonnelOrderDocumentHeader(order.order_id, { expected_document_revision: order.document_revision ?? 1, order_number: number, order_date: orderDate || null, source_title: title || null, source_title_locale: locale as "kk" | "ru" | "unknown", reason_code: reasonCode || null, reason_text: reasonText || null });
      setMessage("Реквизиты сохранены."); await onSaved();
    } catch (error) { setMessage(String(error).includes("409") || String(error).includes("CONFLICT") ? "Приказ был изменён другим пользователем. Обновите данные и повторите действие." : "Не удалось сохранить реквизиты."); }
  }
  return <section data-testid="personnel-order-requisites" className="space-y-3"><h3 className="text-sm font-semibold">Реквизиты</h3>
    <label className="block text-sm">Номер приказа<input aria-label="Номер приказа" value={number} onChange={e=>setNumber(e.target.value)} className="mt-1 w-full rounded border p-2" /></label>
    <label className="block text-sm">Дата приказа<input aria-label="Дата приказа" type="date" value={orderDate} onChange={e=>setOrderDate(e.target.value)} className="mt-1 w-full rounded border p-2" /></label>
    <label className="block text-sm">Исходное название<textarea aria-label="Исходное название" value={title} onChange={e=>setTitle(e.target.value)} className="mt-1 w-full rounded border p-2" /></label>
    <label className="block text-sm">Язык исходного названия<select aria-label="Язык исходного названия" value={locale} onChange={e=>setLocale(e.target.value)} className="mt-1 w-full rounded border p-2"><option value="kk">Қазақша</option><option value="ru">Русский</option><option value="unknown">Неизвестен</option></select></label>
    <label className="block text-sm">Причина исправления<input aria-label="Причина исправления" value={reasonCode} onChange={e=>setReasonCode(e.target.value)} className="mt-1 w-full rounded border p-2" /></label>
    <label className="block text-sm">Пояснение<textarea aria-label="Пояснение" value={reasonText} onChange={e=>setReasonText(e.target.value)} className="mt-1 w-full rounded border p-2" /></label>
    <p className="text-xs text-zinc-500">Ревизия документа: {order.document_revision ?? 1}</p>{message ? <p role="alert">{message}</p> : null}<button type="button" onClick={()=>void save()} className="rounded bg-blue-600 px-3 py-2 text-sm text-white">Сохранить реквизиты</button></section>;
}

const DOCUMENT_ITEM_TYPES = [
  "HIRE", "TRANSFER", "TERMINATION", "CONCURRENT_DUTY_START", "CONCURRENT_DUTY_END",
  "SUPPLEMENTARY_PAY", "RETURN_FROM_CHILDCARE_LEAVE", "LEAVE.ANNUAL.GRANT",
  "LEAVE.UNPAID.GRANT", "LEAVE.CHILDCARE.GRANT",
];

function PersonnelOrderDocumentItemsForm({ detail, onSaved }: { detail: PersonnelOrderDetailResponse; onSaved: () => Promise<void> }) {
  const order = detail.order;
  const [items, setItems] = React.useState<PersonnelOrderDocumentItem[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [message, setMessage] = React.useState<string | null>(null);
  const [reasonCode, setReasonCode] = React.useState("");
  const [reasonText, setReasonText] = React.useState("");
  const registered = ["REGISTERED", "SIGNED"].includes(order.status);

  const load = React.useCallback(async () => {
    setLoading(true);
    try { setItems((await listPersonnelOrderDocumentItems(order.order_id)).items); }
    catch { setMessage("Не удалось загрузить пункты приказа."); }
    finally { setLoading(false); }
  }, [order.order_id]);
  React.useEffect(() => { void load(); }, [load]);

  function change(itemId: number, patch: Partial<PersonnelOrderDocumentItem>) {
    setItems((old) => old.map((item) => item.item_id === itemId ? { ...item, ...patch } : item));
  }
  async function save(item: PersonnelOrderDocumentItem) {
    if (registered && (!reasonCode.trim() || !reasonText.trim())) {
      setMessage("Для зарегистрированного приказа укажите причину и пояснение."); return;
    }
    try {
      const result = await patchPersonnelOrderDocumentItem(order.order_id, item.item_id, {
        expected_document_revision: order.document_revision ?? 1,
        item_type_code: item.item_type_code,
        employee_id: item.employee_id ?? null,
        effective_date: item.effective_date || null,
        reason_code: reasonCode || null,
        reason_text: reasonText || null,
      });
      setMessage(result.no_op ? "Изменений нет." : "Пункт сохранён.");
      await onSaved(); await load();
    } catch (error) {
      setMessage(String(error).includes("409") || String(error).includes("CONFLICT")
        ? "Приказ был изменён другим пользователем. Обновите данные и повторите действие."
        : "Не удалось сохранить пункт.");
    }
  }
  return <section data-testid="personnel-order-document-items" className="space-y-4">
    <h3 className="text-sm font-semibold">Пункты</h3>
    <p className="text-xs text-zinc-500">Редактируются только тип, сотрудник и дата действия. Служебные данные не отображаются.</p>
    {registered ? <><label className="block text-sm">Причина исправления<input aria-label="Причина исправления пункта" value={reasonCode} onChange={(e) => setReasonCode(e.target.value)} className="mt-1 w-full rounded border p-2" /></label><label className="block text-sm">Пояснение<textarea aria-label="Пояснение исправления пункта" value={reasonText} onChange={(e) => setReasonText(e.target.value)} className="mt-1 w-full rounded border p-2" /></label></> : null}
    {message ? <p role="alert">{message}</p> : null}
    {loading ? <p className="text-sm text-zinc-500">Загрузка пунктов…</p> : null}
    {items.map((item) => <article key={item.item_id} className="space-y-2 rounded border border-zinc-200 p-3 dark:border-zinc-800" data-testid={`personnel-order-document-item-${item.item_id}`}>
      <div className="text-sm font-medium">Пункт {item.item_number}</div>
      <label className="block text-sm">Тип пункта<select aria-label={`Тип пункта ${item.item_id}`} value={item.item_type_code} onChange={(e) => change(item.item_id, { item_type_code: e.target.value })} className="mt-1 w-full rounded border p-2">{DOCUMENT_ITEM_TYPES.map((code) => <option key={code} value={code}>{code}</option>)}</select></label>
      <label className="block text-sm">Сотрудник<input aria-label={`Сотрудник ${item.item_id}`} type="number" min="1" value={item.employee_id ?? ""} onChange={(e) => change(item.item_id, { employee_id: e.target.value ? Number(e.target.value) : null })} className="mt-1 w-full rounded border p-2" /></label>
      {item.employee_name ? <p className="text-xs text-zinc-500">{item.employee_name}</p> : null}
      <label className="block text-sm">Дата действия<input aria-label={`Дата действия ${item.item_id}`} type="date" value={item.effective_date || ""} onChange={(e) => change(item.item_id, { effective_date: e.target.value || null })} className="mt-1 w-full rounded border p-2" /></label>
      <button type="button" onClick={() => void save(item)} className="rounded bg-blue-600 px-3 py-2 text-sm text-white">Сохранить пункт</button>
    </article>)}
  </section>;
}

function renderFileLink(path?: string | null, url?: string | null): React.ReactNode {
  const href = String(url || path || "").trim();
  if (!href) return "—";
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="break-all text-blue-700 hover:underline dark:text-blue-300"
      onClick={(e) => e.stopPropagation()}
    >
      {href}
    </a>
  );
}

function formatEventDetails(event: PersonnelOrderLinkedEvent): string[] {
  const typeKey = String(event.event_type || "").toUpperCase();
  const nameOrDash = (v?: string | null) => String(v || "").trim() || "—";
  const fmtRate = (v?: number | null) =>
    v == null || !Number.isFinite(Number(v)) ? "—" : String(parseFloat(Number(v).toFixed(2)));

  if (typeKey === "HIRE") {
    return [
      `Отделение: ${nameOrDash(event.to_org_unit_name)}`,
      `Должность: ${nameOrDash(event.to_position_name)}`,
      `Ставка: ${fmtRate(event.to_rate)}`,
    ];
  }
  if (typeKey === "TERMINATION") {
    return [
      `Отделение: ${nameOrDash(event.from_org_unit_name)}`,
      `Должность: ${nameOrDash(event.from_position_name)}`,
      `Ставка: ${fmtRate(event.from_rate)}`,
    ];
  }
  if (typeKey === "RATE_CHANGE") {
    return [`Ставка: ${fmtRate(event.from_rate)} → ${fmtRate(event.to_rate)}`];
  }
  return [
    `${nameOrDash(event.from_org_unit_name)} → ${nameOrDash(event.to_org_unit_name)}`,
    `${nameOrDash(event.from_position_name)} → ${nameOrDash(event.to_position_name)}`,
    `Ставка: ${fmtRate(event.from_rate)} → ${fmtRate(event.to_rate)}`,
  ];
}

export default function PersonnelOrderDetailDrawer({
  orderId,
  open,
  onClose,
  onChanged,
  hirePersonId = null,
}: Props) {
  const [detail, setDetail] = React.useState<PersonnelOrderDetailResponse | null>(null);
  const [editorial, setEditorial] = React.useState<PersonnelOrderEditorialState | null>(null);
  const [documentReview, setDocumentReview] = React.useState<PersonnelOrderDocumentReview | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<{ message: string; kind: "success" | "error" } | null>(null);
  const [printOpen, setPrintOpen] = React.useState(false);
  const [printBusy, setPrintBusy] = React.useState(false);
  const [printError, setPrintError] = React.useState<string | null>(null);
  const [headerRequisitesDraft, setHeaderRequisitesDraft] =
    React.useState<PersonnelOrderRequisitesSnapshot | null>(null);
  const [activeTab, setActiveTab] = React.useState<"document" | "data" | "requisites" | "items">("document");
  const [orderLanguage, setOrderLanguage] = React.useState<PersonnelOrderDocumentLanguage>("kk");
  const [printLanguage, setPrintLanguage] = React.useState<PersonnelOrderDocumentLanguage | null>(null);

  React.useEffect(() => {
    if (!printLanguage) return;
    const clearPrintRoot = () => setPrintLanguage(null);
    window.addEventListener("afterprint", clearPrintRoot, { once: true });
    return () => window.removeEventListener("afterprint", clearPrintRoot);
  }, [printLanguage]);

  React.useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  const reload = React.useCallback(async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const [body, editorialState, review] = await Promise.all([
        getPersonnelOrder(id), getPersonnelOrderEditorial(id).catch(() => null),
        getPersonnelOrderDocumentReview(id).catch(() => null),
      ]);
      setDetail(body);
      setEditorial(editorialState);
      setDocumentReview(review);
      return body;
    } catch (e) {
      setDetail(null);
      setEditorial(null);
      setDocumentReview(null);
      setError(mapPersonnelOrdersApiError(e, "Не удалось загрузить приказ."));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (!open || orderId == null) {
      setDetail(null);
      setError(null);
      setToast(null);
      setHeaderRequisitesDraft(null);
      setActiveTab("document");
      setOrderLanguage("kk");
      return;
    }
    let cancelled = false;
    void reload(orderId).then((body) => {
      if (cancelled || !body) return;
    });
    return () => {
      cancelled = true;
    };
  }, [open, orderId, reload]);

  function handleChanged(next: PersonnelOrderDetailResponse) {
    setDetail(next);
    setHeaderRequisitesDraft(null);
    onChanged?.(next);
  }

  const handleEditorialChanged = React.useCallback((next: PersonnelOrderEditorialState) => {
    setEditorial(next);
    void reload(next.order_id);
  }, [reload]);

  const handleHeaderRequisitesChange = React.useCallback(
    (snapshot: PersonnelOrderRequisitesSnapshot) => {
      setHeaderRequisitesDraft(snapshot);
    },
    [],
  );

  if (!open || orderId == null) return null;

  const order = detail?.order;
  const previewRequisites = order
    ? mergePersonnelOrderRequisitesForPreview(
        {
          order_date: order.order_date ?? null,
          signed_by_name: order.signed_by_name ?? null,
          signed_by_position: order.signed_by_position ?? null,
        },
        headerRequisitesDraft,
      )
    : null;
  const linkedEventCount = detail?.events.length || 0;
  const applied = isPersonnelOrderApplied(linkedEventCount);
  const editable = order ? isWritablePersonnelOrder(order.status, order.is_archived) : false;
  const sourceTitle = detail?.localized_texts.find((text) => text.title?.trim())?.title?.trim() || "—";
  const documentAvailable = personnelOrderDocumentAvailable(detail, orderLanguage, editorial);
  const basisDocuments = Array.isArray(order?.storage_json?.basis_documents)
    ? order.storage_json.basis_documents
        .filter((basis): basis is Record<string, unknown> => Boolean(basis) && typeof basis === "object")
    : [];
  const reconstructedForReview = order?.storage_json?.reconstruction_status === "NEEDS_DOCX_REVIEW";
  const signatoryRole = normalizePersonnelOrderSignatoryRole(order?.signed_by_position);
  const signatoryPositionLabel = signatoryRole
    ? personnelOrderSignatoryRoleLabel(signatoryRole, "ru")
    : order?.signed_by_position || "—";

  return (
    <div className="fixed inset-0 z-50 flex justify-end" data-testid="personnel-order-detail-drawer">
      <button type="button" aria-label="Закрыть" className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-3xl flex-col border-l border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-4 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              {order ? `Приказ ${formatPersonnelOrderNumber(order.order_number)}` : "Кадровый приказ"}
            </h2>
            {documentReview ? <p data-testid="personnel-order-document-review-status" className="mt-1 text-xs font-medium text-zinc-600">{documentReview.state === "CONFIRMED" ? "Подтверждено кадровой службой" : "Не подтверждено кадровой службой"} · ревизия {documentReview.document_revision}</p> : null}
            {order ? (
              <p className="mt-1 text-xs text-zinc-500">
                {formatPersonnelOrderDate(order.order_date)} · ID {order.order_id}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {orderId != null ? (
              <button
                type="button"
                data-testid="personnel-order-drawer-print"
                onClick={() => {
                  setActiveTab("document");
                  setPrintLanguage(orderLanguage);
                  window.setTimeout(() => window.print(), 50);
                }}
                disabled={!documentAvailable}
                className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
              >
                Печать
              </button>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
            >
              Закрыть
            </button>
          </div>
        </div>

        <div className="flex gap-1 border-b border-zinc-200 px-4 pt-3 dark:border-zinc-800" role="tablist" aria-label="Карточка приказа">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "document"}
            onClick={() => setActiveTab("document")}
            className={`rounded-t-lg px-3 py-2 text-sm font-medium ${activeTab === "document" ? "bg-zinc-100 text-zinc-950 dark:bg-zinc-800 dark:text-zinc-50" : "text-zinc-500"}`}
          >
            Документ
          </button>
          <button type="button" role="tab" aria-selected={activeTab === "requisites"} onClick={() => setActiveTab("requisites")} className={`rounded-t-lg px-3 py-2 text-sm font-medium ${activeTab === "requisites" ? "bg-zinc-100 text-zinc-950" : "text-zinc-500"}`}>Реквизиты</button>
          <button type="button" role="tab" aria-selected={activeTab === "items"} onClick={() => setActiveTab("items")} className={`rounded-t-lg px-3 py-2 text-sm font-medium ${activeTab === "items" ? "bg-zinc-100 text-zinc-950" : "text-zinc-500"}`}>Пункты</button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "data"}
            onClick={() => setActiveTab("data")}
            className={`rounded-t-lg px-3 py-2 text-sm font-medium ${activeTab === "data" ? "bg-zinc-100 text-zinc-950 dark:bg-zinc-800 dark:text-zinc-50" : "text-zinc-500"}`}
          >
            Данные
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-4 py-4">
          {order ? (
            <div
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-zinc-200 px-3 py-2 dark:border-zinc-800"
              role="group"
              aria-label="Язык приказа"
              data-testid="personnel-order-language-switcher"
            >
              <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">Язык приказа</span>
              <div className="flex gap-1">
                <button type="button" onClick={() => setOrderLanguage("kk")} aria-pressed={orderLanguage === "kk"} className={`rounded px-2 py-1 text-sm ${orderLanguage === "kk" ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900" : "text-zinc-600 dark:text-zinc-300"}`}>Қазақша</button>
                <button type="button" onClick={() => setOrderLanguage("ru")} aria-pressed={orderLanguage === "ru"} className={`rounded px-2 py-1 text-sm ${orderLanguage === "ru" ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900" : "text-zinc-600 dark:text-zinc-300"}`}>Русский</button>
              </div>
            </div>
          ) : null}
          {reconstructedForReview ? (
            <div
              data-testid="personnel-order-reconstruction-warning"
              className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100"
            >
              Восстановлено по журналу. Автоматически подставленные сведения требуют сверки с DOCX
            </div>
          ) : null}
          {toast ? (
            <div
              className={
                toast.kind === "error"
                  ? "rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200"
                  : "rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900 dark:border-emerald-900/55 dark:bg-emerald-950/35 dark:text-emerald-100"
              }
            >
              {toast.message}
            </div>
          ) : null}

          {loading ? <div className="text-sm text-zinc-500">Загрузка приказа…</div> : null}

          {error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
              {error}
            </div>
          ) : null}

          {order && activeTab === "document" ? (
            <PersonnelOrderDocumentView detail={detail} language={orderLanguage} editorial={editorial} />
          ) : null}
          {order && activeTab === "requisites" && detail ? <PersonnelOrderDocumentHeaderForm detail={detail} onSaved={async () => { const next = await reload(order.order_id); if (next) onChanged?.(next); }} /> : null}
          {order && activeTab === "items" && detail ? <PersonnelOrderDocumentItemsForm detail={detail} onSaved={async () => { const next = await reload(order.order_id); if (next) onChanged?.(next); }} /> : null}

          {order && activeTab === "data" ? (
            <>
              {documentReview ? <section data-testid="personnel-order-document-review">
                <h3 className="mb-2 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Проверка документа</h3>
                {documentReview.blockers.length || documentReview.warnings.length ? <ul className="mb-3 space-y-1 text-sm text-amber-800">{[...documentReview.blockers, ...documentReview.warnings].map((entry, index) => <li key={`${entry.code}-${index}`}>{entry.code}</li>)}</ul> : null}
                <div className="flex flex-wrap gap-2">
                  {documentReview.allowed_actions.includes("confirm") ? <button type="button" className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white" onClick={async () => { const next = await confirmPersonnelOrderDocumentReview(order.order_id, { expected_document_revision: documentReview.document_revision, reason_code: "HR_DOCUMENT_REVIEW" }); setDocumentReview(next); await reload(order.order_id); }}>Подтвердить кадровой службой</button> : null}
                  {documentReview.allowed_actions.includes("reopen") ? <button type="button" className="rounded border border-amber-500 px-3 py-1.5 text-sm" onClick={async () => { const note = window.prompt("Пояснение для возврата на проверку"); if (!note?.trim()) return; const next = await reopenPersonnelOrderDocumentReview(order.order_id, { expected_document_revision: documentReview.document_revision, reason_code: "HR_DOCUMENT_REOPEN", note }); setDocumentReview(next); await reload(order.order_id); }}>Вернуть на проверку</button> : null}
                </div>
              </section> : null}
              <section>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Действия</h3>
                <PersonnelOrderLifecycleActions
                  order={order}
                  itemCount={detail?.items.length || 0}
                  linkedEventCount={linkedEventCount}
                  onChanged={handleChanged}
                  onToast={(message, kind = "success") => setToast({ message, kind })}
                />
              </section>

              <section>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Заголовок</h3>
                <div className="mb-3">
                  <Field label="Исходное название" value={sourceTitle} />
                </div>
                {editable ? (
                  <PersonnelOrderHeaderEditor
                    order={order}
                    onSaved={handleChanged}
                    onRequisitesChange={handleHeaderRequisitesChange}
                  />
                ) : (
                  <>
                    <div className="mb-3">
                      <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                        Тип приказа
                      </div>
                      <div className="mt-1 flex flex-wrap gap-2">
                        <PersonnelOrderTypeBadge typeCode={order.order_type_code} />
                        <PersonnelOrderStatusBadge status={order.status} />
                        {applied ? <PersonnelOrderAppliedBadge /> : null}
                        {order.is_archived ? <PersonnelOrderArchivedBadge /> : null}
                      </div>
                    </div>
                    <dl className="grid gap-3 sm:grid-cols-2">
                    <Field label="№ приказа" value={formatPersonnelOrderNumber(order.order_number)} />
                    <Field label="Дата приказа" value={formatPersonnelOrderDate(order.order_date)} />
                    <Field label="Должность подписанта" value={signatoryPositionLabel} />
                    <Field label="ФИО подписанта" value={order.signed_by_name || "—"} />
                    <Field label="Источник" value={personnelOrderSourceModeLabel(order.source_mode)} />
                    <Field label="Основание" value={order.legal_basis_article || order.basis_summary || "—"} />
                    <Field label="Комментарий" value={order.comment || "—"} />
                    {order.void_reason ? (
                      <>
                        <Field label="Причина аннулирования" value={order.void_reason} />
                        <Field label="Аннулирован" value={formatPersonnelOrderDateTime(order.voided_at)} />
                      </>
                    ) : null}
                  </dl>
                  </>
                )}
              </section>

              {order.is_archived ? (
                <section data-testid="personnel-order-archive-block">
                  <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Архивирование</h3>
                  <dl className="grid gap-3 sm:grid-cols-2">
                    <Field
                      label="Дата архивирования"
                      value={formatPersonnelOrderDateTime(order.archive_summary_at)}
                    />
                    <Field label="Пользователь" value={order.archive_summary_by_name || "—"} />
                    <Field label="Причина" value={order.archive_summary_reason || "—"} />
                  </dl>
                </section>
              ) : null}

              <section>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Пункты приказа</h3>
                <p className="mb-3 text-xs text-zinc-500">
                  Каждый пункт имеет собственный тип. Тип пункта не дублирует тип приказа в заголовке.
                </p>
                <PersonnelOrderItemEditor
                  orderId={order.order_id}
                  orderTypeCode={order.order_type_code}
                  items={detail?.items || []}
                  disabled={!editable}
                  onChanged={handleChanged}
                  hirePersonId={hirePersonId}
                  basisDocuments={basisDocuments}
                />
              </section>

              {detail ? <PersonnelOrderAcknowledgements detail={detail} onChanged={handleChanged} /> : null}

              <section>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Связанные события ({detail?.events.length || 0})
                </h3>
                {(detail?.events.length || 0) === 0 ? (
                  <p className="text-sm text-zinc-500">События не созданы.</p>
                ) : (
                  <div className="space-y-3">
                    {detail?.events.map((event) => (
                      <div key={event.event_id} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                            {event.event_label || event.event_type}
                          </span>
                          <span className="rounded border border-zinc-200 px-1.5 py-0.5 text-xs text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
                            {event.lifecycle_status}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-zinc-500">
                          {event.employee_name || `#${event.employee_id}`} ·{" "}
                          {formatPersonnelOrderDate(event.effective_date)}
                        </p>
                        <ul className="mt-2 space-y-0.5 text-xs text-zinc-600 dark:text-zinc-400">
                          {formatEventDetails(event).map((line) => (
                            <li key={line}>{line}</li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section>
                <PersonnelOrderEditorialTextEditor
                  orderId={order.order_id}
                  order={previewRequisites ?? order}
                  items={detail?.items || []}
                  editable={editable}
                  basisDocuments={basisDocuments}
                  onOrderChanged={handleChanged}
                  onEditorialChanged={handleEditorialChanged}
                  locale={orderLanguage}
                />
              </section>

              <section>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Вложения ({detail?.attachments.length || 0})
                </h3>
                <p className="text-sm text-zinc-500">Загрузка вложений — WP-PO-009.</p>
                {(detail?.attachments.length || 0) > 0 ? (
                  <div className="mt-3 space-y-2">
                    {detail?.attachments.map((attachment) => (
                      <div
                        key={attachment.attachment_id}
                        className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800"
                      >
                        <div className="font-medium">{attachment.attachment_kind}</div>
                        <div className="mt-1">{renderFileLink(attachment.file_path, attachment.file_url)}</div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </section>
            </>
          ) : null}
        </div>
      </aside>

      <PersonnelOrderPrintLanguageDialog
        open={printOpen}
        onClose={() => {
          if (printBusy) return;
          setPrintOpen(false);
        }}
        busy={printBusy}
        onConfirm={async (language: PersonnelOrderPrintLanguage, action: PersonnelOrderPrintDialogAction) => {
          if (orderId == null) return;
          if (action === "preview") {
            setPrintOpen(false);
            setPrintBusy(true);
            setPrintError(null);
            try {
              const fresh = await getPersonnelOrder(orderId);
              setDetail(fresh);
              const draft = headerRequisitesDraft;
              const savedSignatory = resolvePersonnelOrderSignatoryDisplay(fresh.order);
              const draftSignatory = draft ? resolvePersonnelOrderSignatoryDisplay(draft) : null;
              const draftDiffersFromSaved = Boolean(
                draft &&
                  ((draft.signed_by_name || "") !== (fresh.order.signed_by_name || "") ||
                    (draft.signed_by_position || "") !== (fresh.order.signed_by_position || "") ||
                    (draft.order_date || "") !== (fresh.order.order_date || "")),
              );
              if (draftDiffersFromSaved) {
                setPrintError("Сохраните заголовок приказа перед предпросмотром.");
                return;
              }
              if (!hasPersonnelOrderSignatory(savedSignatory)) {
                if (draft && hasPersonnelOrderSignatory(draftSignatory!)) {
                  setPrintError("Сохраните заголовок приказа перед предпросмотром.");
                  return;
                }
                setPrintError(
                  "Реквизиты подписанта не сохранены. Заполните и сохраните заголовок приказа.",
                );
                return;
              }
              setHeaderRequisitesDraft(null);
              const opened = openPersonnelOrderPrintPreview(
                orderId,
                language,
                fresh.order.updated_at || Date.now(),
              );
              setPrintError(opened ? null : PERSONNEL_ORDER_PRINT_POPUP_BLOCKED_MESSAGE);
            } catch (e) {
              setPrintError(mapPersonnelOrdersApiError(e, "Не удалось подготовить предпросмотр."));
            } finally {
              setPrintBusy(false);
            }
            return;
          }
          setPrintBusy(true);
          setPrintError(null);
          const result = await openPersonnelOrderPdf(orderId, language);
          setPrintBusy(false);
          if (result.ok) {
            setPrintOpen(false);
            return;
          }
          setPrintError(result.error);
        }}
      />
      {printError ? (
        <div
          className="fixed bottom-4 right-4 z-[70] max-w-sm rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 shadow-lg dark:border-red-900/55 dark:bg-red-950/90 dark:text-red-100"
          data-testid="personnel-order-drawer-pdf-error"
        >
          {printError}
        </div>
      ) : null}
      {printLanguage && detail
        ? createPortal(
            <PersonnelOrderDocumentView detail={detail} language={printLanguage} editorial={editorial} printRoot />,
            document.body,
          )
        : null}
    </div>
  );
}
