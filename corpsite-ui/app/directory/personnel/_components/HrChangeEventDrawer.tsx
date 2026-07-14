"use client";

import * as React from "react";
import Link from "next/link";

import { buildEmployeeCardHref } from "@/lib/employeeCardNav";

import {
  formatHrChangeEventDate,
  formatHrChangeEventValue,
  hrChangeEventFieldLabel,
  hrChangeEventTypeLabel,
  type HrChangeEventRow,
} from "../_lib/hrChangeEventsApi.client";
import HrChangeEventTypeBadge from "./HrChangeEventTypeBadge";

type Props = {
  event: HrChangeEventRow | null;
  open: boolean;
  onClose: () => void;
};

function renderDetails(details: Record<string, unknown> | null): React.ReactNode {
  if (!details || Object.keys(details).length === 0) {
    return <span className="text-zinc-500">—</span>;
  }
  return (
    <pre className="max-h-48 overflow-auto rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-800 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200">
      {JSON.stringify(details, null, 2)}
    </pre>
  );
}

export default function HrChangeEventDrawer({ event, open, onClose }: Props) {
  React.useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open || !event) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="Закрыть"
        className="absolute inset-0 bg-black/30"
        onClick={onClose}
      />
      <aside className="relative flex h-full w-full max-w-lg flex-col border-l border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-4 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              {event.full_name || "Событие изменения реестра"}
            </h2>
            <p className="mt-1 text-xs text-zinc-500">{formatHrChangeEventDate(event.event_at)}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
          >
            Закрыть
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">Тип события</div>
            <div className="mt-1">
              <HrChangeEventTypeBadge eventType={event.event_type} />
            </div>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              {hrChangeEventTypeLabel(event.event_type)}
            </p>
          </div>

          <dl className="grid gap-3 text-sm">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">ИИН</dt>
              <dd className="mt-0.5 font-mono text-sm text-zinc-800 dark:text-zinc-200">
                {event.iin || "—"}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">Отделение</dt>
              <dd className="mt-0.5 text-zinc-800 dark:text-zinc-200">
                {formatHrChangeEventValue(event.department)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">Поле</dt>
              <dd className="mt-0.5 text-zinc-800 dark:text-zinc-200">
                {hrChangeEventFieldLabel(event.field_name, event.record_kind)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">Было</dt>
              <dd className="mt-0.5 whitespace-pre-wrap text-zinc-800 dark:text-zinc-200">
                {formatHrChangeEventValue(event.old_value)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">Стало</dt>
              <dd className="mt-0.5 whitespace-pre-wrap text-zinc-800 dark:text-zinc-200">
                {formatHrChangeEventValue(event.new_value)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">Details</dt>
              <dd className="mt-1">{renderDetails(event.details)}</dd>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  prior_snapshot_id
                </dt>
                <dd className="mt-0.5 font-mono text-xs text-zinc-800 dark:text-zinc-200">
                  {event.prior_snapshot_id}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  new_snapshot_id
                </dt>
                <dd className="mt-0.5 font-mono text-xs text-zinc-800 dark:text-zinc-200">
                  {event.new_snapshot_id}
                </dd>
              </div>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">match_key</dt>
              <dd className="mt-0.5 break-all font-mono text-xs text-zinc-600 dark:text-zinc-400">
                {event.match_key}
              </dd>
            </div>
          </dl>

          {event.employee_id != null ? (
            <Link
              href={buildEmployeeCardHref(event.employee_id)}
              className="inline-flex text-sm font-medium text-blue-700 hover:underline dark:text-blue-300"
            >
              Карточка сотрудника
            </Link>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
