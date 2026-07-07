"use client";

import * as React from "react";

import {
  formatPersonnelOrderDate,
  formatPersonnelOrderDateTime,
  getPersonnelOrder,
  mapPersonnelOrdersApiError,
  personnelOrderSourceModeLabel,
  type PersonnelOrderDetailResponse,
  type PersonnelOrderLinkedEvent,
} from "../_lib/personnelOrdersApi.client";
import PersonnelOrderStatusBadge from "./PersonnelOrderStatusBadge";
import PersonnelOrderTypeBadge from "./PersonnelOrderTypeBadge";

type Props = {
  orderId: number | null;
  open: boolean;
  onClose: () => void;
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
    return [
      `Ставка: ${fmtRate(event.from_rate)} → ${fmtRate(event.to_rate)}`,
    ];
  }
  return [
    `${nameOrDash(event.from_org_unit_name)} → ${nameOrDash(event.to_org_unit_name)}`,
    `${nameOrDash(event.from_position_name)} → ${nameOrDash(event.to_position_name)}`,
    `Ставка: ${fmtRate(event.from_rate)} → ${fmtRate(event.to_rate)}`,
  ];
}

export default function PersonnelOrderDetailDrawer({ orderId, open, onClose }: Props) {
  const [detail, setDetail] = React.useState<PersonnelOrderDetailResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  React.useEffect(() => {
    if (!open || orderId == null) {
      setDetail(null);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    getPersonnelOrder(orderId)
      .then((body) => {
        if (cancelled) return;
        setDetail(body);
      })
      .catch((e) => {
        if (cancelled) return;
        setDetail(null);
        setError(mapPersonnelOrdersApiError(e, "Не удалось загрузить приказ."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, orderId]);

  if (!open || orderId == null) return null;

  const order = detail?.order;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" data-testid="personnel-order-detail-drawer">
      <button
        type="button"
        aria-label="Закрыть"
        className="absolute inset-0 bg-black/30"
        onClick={onClose}
      />
      <aside className="relative flex h-full w-full max-w-2xl flex-col border-l border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-4 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              {order ? `Приказ ${order.order_number}` : "Кадровый приказ"}
            </h2>
            {order ? (
              <p className="mt-1 text-xs text-zinc-500">
                {formatPersonnelOrderDate(order.order_date)} · ID {order.order_id}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
          >
            Закрыть
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-4 py-4">
          {loading ? (
            <div className="text-sm text-zinc-500">Загрузка приказа…</div>
          ) : null}

          {error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
              {error}
            </div>
          ) : null}

          {order ? (
            <>
              <section>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Заголовок</h3>
                <div className="mb-3 flex flex-wrap gap-2">
                  <PersonnelOrderTypeBadge typeCode={order.order_type_code} />
                  <PersonnelOrderStatusBadge status={order.status} />
                </div>
                <dl className="grid gap-3 sm:grid-cols-2">
                  <Field label="Дата приказа" value={formatPersonnelOrderDate(order.order_date)} />
                  <Field label="Источник" value={personnelOrderSourceModeLabel(order.source_mode)} />
                  <Field label="Подписант" value={order.signed_by_name || "—"} />
                  <Field label="Должность подписанта" value={order.signed_by_position || "—"} />
                  <Field label="Основание" value={order.legal_basis_article || order.basis_summary || "—"} />
                  <Field label="Исполнитель" value={order.executor_name || "—"} />
                  <Field label="Комментарий" value={order.comment || "—"} />
                  {order.void_reason ? (
                    <>
                      <Field label="Причина аннулирования" value={order.void_reason} />
                      <Field label="Аннулирован" value={formatPersonnelOrderDateTime(order.voided_at)} />
                    </>
                  ) : null}
                </dl>
              </section>

              <section>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Пункты ({detail?.items.length || 0})
                </h3>
                {(detail?.items.length || 0) === 0 ? (
                  <p className="text-sm text-zinc-500">Пункты отсутствуют.</p>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
                    <table className="min-w-full text-sm">
                      <thead className="bg-zinc-50 dark:bg-zinc-900/50">
                        <tr>
                          {["№", "Тип", "Сотрудник", "Дата", "Статус"].map((h) => (
                            <th key={h} className="px-3 py-2 text-left text-[11px] font-semibold uppercase text-zinc-500">
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                        {detail?.items.map((item) => (
                          <tr key={item.item_id}>
                            <td className="px-3 py-2">{item.item_number}</td>
                            <td className="px-3 py-2">
                              <PersonnelOrderTypeBadge typeCode={item.item_type_code} />
                            </td>
                            <td className="px-3 py-2">{item.employee_name || (item.employee_id ? `#${item.employee_id}` : "—")}</td>
                            <td className="px-3 py-2">{formatPersonnelOrderDate(item.effective_date)}</td>
                            <td className="px-3 py-2">{item.item_status}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
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
                      <div
                        key={event.event_id}
                        className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                            {event.event_label || event.event_type}
                          </span>
                          <span className="rounded border border-zinc-200 px-1.5 py-0.5 text-xs text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
                            {event.lifecycle_status}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-zinc-500">
                          {event.employee_name || `#${event.employee_id}`} · {formatPersonnelOrderDate(event.effective_date)}
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
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Тексты ({detail?.localized_texts.length || 0})
                </h3>
                {(detail?.localized_texts.length || 0) === 0 ? (
                  <p className="text-sm text-zinc-500">Тексты не добавлены.</p>
                ) : (
                  <div className="space-y-3">
                    {detail?.localized_texts.map((textRow) => (
                      <div key={textRow.localized_text_id} className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
                        <div className="text-xs font-medium uppercase text-zinc-500">
                          {textRow.locale}
                          {textRow.is_authoritative ? " · авторитетный" : ""}
                        </div>
                        {textRow.title ? <div className="mt-1 text-sm font-medium">{textRow.title}</div> : null}
                        {textRow.body_text ? (
                          <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-zinc-700 dark:text-zinc-300">
                            {textRow.body_text}
                          </pre>
                        ) : (
                          <p className="mt-2 text-sm text-zinc-500">Текст не заполнен.</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Вложения ({detail?.attachments.length || 0})
                </h3>
                {(detail?.attachments.length || 0) === 0 ? (
                  <p className="text-sm text-zinc-500">Вложения отсутствуют.</p>
                ) : (
                  <div className="space-y-2">
                    {detail?.attachments.map((attachment) => (
                      <div key={attachment.attachment_id} className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
                        <div className="font-medium">{attachment.attachment_kind}</div>
                        <div className="mt-1 text-xs text-zinc-500">{attachment.storage_type}</div>
                        <div className="mt-1">{renderFileLink(attachment.file_path, attachment.file_url)}</div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section>
                <h3 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  Печатные формы ({detail?.prints.length || 0})
                </h3>
                {(detail?.prints.length || 0) === 0 ? (
                  <p className="text-sm text-zinc-500">Печатные формы отсутствуют.</p>
                ) : (
                  <div className="space-y-2">
                    {detail?.prints.map((printRow) => (
                      <div key={printRow.print_id} className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-800">
                        <div className="font-medium">
                          {printRow.locale.toUpperCase()} · {printRow.format}
                          {printRow.is_signed_copy ? " · подписанная копия" : ""}
                        </div>
                        <div className="mt-1 text-xs text-zinc-500">
                          v{printRow.render_version} · {formatPersonnelOrderDateTime(printRow.generated_at)}
                        </div>
                        <div className="mt-1">{renderFileLink(printRow.file_path, printRow.file_url)}</div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
