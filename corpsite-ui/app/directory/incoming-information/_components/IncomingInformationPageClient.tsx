"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";

import { INCOMING_INFORMATION_NAV_HREF } from "@/lib/incomingInformationNav";

import {
  incomingInformationErrorMessage,
  incomingInformationErrorStatus,
  listIncomingDocuments,
} from "../_lib/api.client";
import type { IncomingDocumentListItem } from "../_lib/types";

export const INCOMING_DOCUMENTS_PAGE_LIMIT = 25;

export function parseIncomingInformationOffset(value: string | null): number {
  if (value == null || value === "") return 0;
  if (!/^\d+$/.test(value)) return 0;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0) return 0;
  return parsed;
}

export function buildIncomingInformationListHref(offset: number): string {
  const normalized = Number.isSafeInteger(offset) && offset > 0 ? offset : 0;
  return normalized > 0
    ? `${INCOMING_INFORMATION_NAV_HREF}?offset=${normalized}`
    : INCOMING_INFORMATION_NAV_HREF;
}

function formatDate(value: string | null, withTime = false): string {
  if (!value) return "—";
  if (!withTime && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split("-");
    return `${day}.${month}.${year}`;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return withTime ? date.toLocaleString("ru-RU") : date.toLocaleDateString("ru-RU");
}

function DocumentTable({ items }: { items: IncomingDocumentListItem[] }) {
  return (
    <div
      className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800"
      data-testid="incoming-information-table"
    >
      <table className="min-w-[1180px] divide-y divide-zinc-200 text-sm dark:divide-zinc-800">
        <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900/60">
          <tr>
            <th className="px-3 py-3">Рег. номер</th>
            <th className="px-3 py-3">Дата регистрации</th>
            <th className="px-3 py-3">Тип</th>
            <th className="px-3 py-3">Отправитель</th>
            <th className="min-w-[22rem] px-3 py-3">Краткое содержание</th>
            <th className="px-3 py-3">Основной исполнитель</th>
            <th className="px-3 py-3">Срок</th>
            <th className="px-3 py-3">Статус</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100 dark:divide-zinc-900">
          {items.map((item) => (
            <tr key={item.incoming_document_id} data-testid={`incoming-information-row-${item.incoming_document_id}`}>
              <td className="whitespace-nowrap px-3 py-3 align-top">
                <Link
                  href={`${INCOMING_INFORMATION_NAV_HREF}/documents/${item.incoming_document_id}`}
                  className="font-medium text-blue-700 hover:underline dark:text-blue-300"
                >
                  {item.registration_number}
                </Link>
              </td>
              <td className="whitespace-nowrap px-3 py-3 align-top">{formatDate(item.registered_at, true)}</td>
              <td className="px-3 py-3 align-top">{item.document_type_label}</td>
              <td className="px-3 py-3 align-top">{item.sender_display}</td>
              <td className="px-3 py-3 align-top">
                <span className="line-clamp-3 whitespace-pre-wrap">{item.summary}</span>
              </td>
              <td className="px-3 py-3 align-top">{item.primary_executor_display || "—"}</td>
              <td className="whitespace-nowrap px-3 py-3 align-top">
                <div>{formatDate(item.due_date)}</div>
                {item.is_overdue ? (
                  <span
                    className="mt-1 inline-flex rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800 dark:bg-red-950/50 dark:text-red-200"
                    data-testid={`incoming-information-overdue-${item.incoming_document_id}`}
                  >
                    Просрочено
                  </span>
                ) : null}
              </td>
              <td className="px-3 py-3 align-top">{item.status_label}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type LoadError = { kind: "forbidden" | "generic"; message: string } | null;

export default function IncomingInformationPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const rawOffset = searchParams.get("offset");
  const offset = parseIncomingInformationOffset(rawOffset);
  const invalidOffset = rawOffset != null && String(offset) !== rawOffset;
  const [items, setItems] = React.useState<IncomingDocumentListItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<LoadError>(null);
  const [retryVersion, setRetryVersion] = React.useState(0);

  React.useEffect(() => {
    if (invalidOffset) router.replace(INCOMING_INFORMATION_NAV_HREF);
  }, [invalidOffset, router]);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    void listIncomingDocuments({ limit: INCOMING_DOCUMENTS_PAGE_LIMIT, offset })
      .then((body) => {
        if (cancelled) return;
        setItems(Array.isArray(body.items) ? body.items : []);
        setTotal(Number.isFinite(body.total) ? body.total : 0);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setItems([]);
        setTotal(0);
        const status = incomingInformationErrorStatus(caught);
        if (status === 401) {
          router.replace("/login");
          return;
        }
        if (status === 403) {
          setError({
            kind: "forbidden",
            message: "Нет доступа к реестру входящей информации.",
          });
          return;
        }
        setError({
          kind: "generic",
          message: incomingInformationErrorMessage(
            caught,
            "Не удалось загрузить входящую информацию.",
          ),
        });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [offset, retryVersion, router]);

  const page = Math.floor(offset / INCOMING_DOCUMENTS_PAGE_LIMIT) + 1;
  const pageCount = Math.max(1, Math.ceil(total / INCOMING_DOCUMENTS_PAGE_LIMIT));

  return (
    <div className="space-y-4 p-4" data-testid="incoming-information-page">
      <div>
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Входящая информация</h1>
        <p className="mt-1 text-sm text-zinc-500">Read-only реестр доступных вам входящих документов.</p>
      </div>

      {loading ? (
        <div
          className="h-28 animate-pulse rounded-xl bg-zinc-100 dark:bg-zinc-900"
          data-testid="incoming-information-loading"
        />
      ) : error?.kind === "forbidden" ? (
        <div
          className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-6 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100"
          data-testid="incoming-information-forbidden"
        >
          <h2 className="font-semibold">Доступ запрещён</h2>
          <p className="mt-2">{error.message}</p>
        </div>
      ) : error ? (
        <div
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200"
          data-testid="incoming-information-error"
        >
          <p>{error.message}</p>
          <button
            type="button"
            onClick={() => setRetryVersion((value) => value + 1)}
            className="mt-3 rounded-lg border border-red-300 px-3 py-1.5 font-medium dark:border-red-800"
          >
            Повторить
          </button>
        </div>
      ) : items.length === 0 ? (
        <div
          className="rounded-xl border border-dashed border-zinc-300 px-4 py-10 text-center text-sm text-zinc-500 dark:border-zinc-700"
          data-testid="incoming-information-empty"
        >
          Доступных входящих документов нет.
        </div>
      ) : (
        <DocumentTable items={items} />
      )}

      {!loading && !error ? (
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-zinc-600 dark:text-zinc-400">
          <span data-testid="incoming-information-total">
            Всего: {total} · страница {page} из {pageCount}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={offset <= 0}
              onClick={() =>
                router.push(
                  buildIncomingInformationListHref(
                    Math.max(0, offset - INCOMING_DOCUMENTS_PAGE_LIMIT),
                  ),
                )
              }
              className="rounded-lg border border-zinc-300 px-3 py-1.5 disabled:opacity-50 dark:border-zinc-700"
              data-testid="incoming-information-page-prev"
            >
              Назад
            </button>
            <button
              type="button"
              disabled={offset + INCOMING_DOCUMENTS_PAGE_LIMIT >= total}
              onClick={() =>
                router.push(
                  buildIncomingInformationListHref(offset + INCOMING_DOCUMENTS_PAGE_LIMIT),
                )
              }
              className="rounded-lg border border-zinc-300 px-3 py-1.5 disabled:opacity-50 dark:border-zinc-700"
              data-testid="incoming-information-page-next"
            >
              Вперёд
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
