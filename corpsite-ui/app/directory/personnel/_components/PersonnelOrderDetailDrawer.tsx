"use client";

import * as React from "react";

import {
  formatPersonnelOrderDate,
  formatPersonnelOrderDateTime,
  formatPersonnelOrderNumber,
  getPersonnelOrder,
  isEditablePersonnelOrderStatus,
  isWritablePersonnelOrder,
  isPersonnelOrderApplied,
  mapPersonnelOrdersApiError,
  personnelOrderSourceModeLabel,
  type PersonnelOrderDetailResponse,
  type PersonnelOrderLinkedEvent,
} from "../_lib/personnelOrdersApi.client";
import PersonnelOrderAppliedBadge from "./PersonnelOrderAppliedBadge";
import PersonnelOrderArchivedBadge from "./PersonnelOrderArchivedBadge";
import PersonnelOrderEditorialTextEditor from "./PersonnelOrderEditorialTextEditor";
import PersonnelOrderHeaderEditor from "./PersonnelOrderHeaderEditor";
import PersonnelOrderItemEditor from "./PersonnelOrderItemEditor";
import PersonnelOrderLifecycleActions from "./PersonnelOrderLifecycleActions";
import PersonnelOrderStatusBadge from "./PersonnelOrderStatusBadge";
import PersonnelOrderTypeBadge from "./PersonnelOrderTypeBadge";
import PersonnelOrderPrintLanguageDialog, {
  type PersonnelOrderPrintDialogAction,
} from "./print/PersonnelOrderPrintLanguageDialog";
import {
  buildPersonnelOrderPrintHref,
  type PersonnelOrderPrintLanguage,
} from "../_lib/personnelOrderPrintLanguage";
import { openPersonnelOrderPdf } from "../_lib/personnelOrderPdfOpen.client";

type Props = {
  orderId: number | null;
  open: boolean;
  onClose: () => void;
  onChanged?: (detail: PersonnelOrderDetailResponse) => void;
};

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-0.5 text-sm text-zinc-800 dark:text-zinc-200">{value}</dd>
    </div>
  );
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

export default function PersonnelOrderDetailDrawer({ orderId, open, onClose, onChanged }: Props) {
  const [detail, setDetail] = React.useState<PersonnelOrderDetailResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toast, setToast] = React.useState<{ message: string; kind: "success" | "error" } | null>(null);
  const [printOpen, setPrintOpen] = React.useState(false);
  const [printBusy, setPrintBusy] = React.useState(false);
  const [printError, setPrintError] = React.useState<string | null>(null);

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
      const body = await getPersonnelOrder(id);
      setDetail(body);
      return body;
    } catch (e) {
      setDetail(null);
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
    onChanged?.(next);
  }

  if (!open || orderId == null) return null;

  const order = detail?.order;
  const linkedEventCount = detail?.events.length || 0;
  const applied = isPersonnelOrderApplied(linkedEventCount);
  const editable = order ? isWritablePersonnelOrder(order.status, order.is_archived) : false;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" data-testid="personnel-order-detail-drawer">
      <button type="button" aria-label="Закрыть" className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-3xl flex-col border-l border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-4 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              {order ? `Приказ ${formatPersonnelOrderNumber(order.order_number)}` : "Кадровый приказ"}
            </h2>
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
                onClick={() => setPrintOpen(true)}
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

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-4 py-4">
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

          {order ? (
            <>
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
                {editable ? (
                  <PersonnelOrderHeaderEditor order={order} onSaved={handleChanged} />
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
                    <Field label="Источник" value={personnelOrderSourceModeLabel(order.source_mode)} />
                    <Field label="Подписант" value={order.signed_by_name || "—"} />
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
                />
              </section>

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
                  items={detail?.items || []}
                  editable={editable}
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
            setPrintError(null);
            window.open(buildPersonnelOrderPrintHref(orderId, language), "_blank", "noopener,noreferrer");
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
    </div>
  );
}
