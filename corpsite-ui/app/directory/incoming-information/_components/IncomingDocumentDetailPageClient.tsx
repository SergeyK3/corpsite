"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";

import { INCOMING_INFORMATION_NAV_HREF } from "@/lib/incomingInformationNav";

import {
  getIncomingDocument,
  incomingInformationErrorMessage,
  incomingInformationErrorStatus,
} from "../_lib/api.client";
import type { IncomingDocumentDetail } from "../_lib/types";

export function parseIncomingDocumentId(value: string): number | null {
  if (!/^\d+$/.test(value)) return null;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) return null;
  return parsed;
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

function referenceLabel(kind: string, text: string | null, references: Array<[string, number | null]>): string {
  if (text) return text;
  const reference = references.find(([, id]) => id != null);
  return reference ? `${kind} · ${reference[0]} #${reference[1]}` : kind;
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="mt-1 whitespace-pre-wrap text-sm text-zinc-900 dark:text-zinc-100">{value ?? "—"}</dd>
    </div>
  );
}

function CardSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
      <h2 className="text-base font-semibold">{title}</h2>
      <dl className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{children}</dl>
    </section>
  );
}

function DetailCard({ document }: { document: IncomingDocumentDetail }) {
  const sender = referenceLabel(document.sender_kind, document.sender_text, [
    ["person", document.sender_person_id],
    ["employee", document.sender_employee_id],
    ["org unit", document.sender_org_unit_id],
  ]);
  const addressee = referenceLabel(document.addressee_kind, document.addressee_text, [
    ["user", document.addressee_user_id],
    ["employee", document.addressee_employee_id],
    ["org unit", document.addressee_org_unit_id],
    ["position", document.addressee_position_id],
  ]);

  return (
    <div className="space-y-4" data-testid="incoming-document-detail">
      <CardSection title="Регистрационные данные">
        <Field label="Регистрационный номер" value={document.registration_number} />
        <Field label="Дата поступления" value={formatDate(document.received_at)} />
        <Field label="Дата регистрации" value={formatDate(document.registered_at, true)} />
        <Field label="Тип документа" value={document.document_type_label} />
        <Field label="Канал поступления" value={document.receipt_channel_label} />
        <Field label="Статус" value={document.status_label} />
        <Field label="Уровень доступа" value={document.access_level} />
        <Field label="Подразделение регистрации" value={`#${document.registration_org_unit_id}`} />
        <Field label="Ответственное подразделение" value={`#${document.responsible_org_unit_id}`} />
        <Field label="Отправитель" value={sender} />
        <Field label="Адресат" value={addressee} />
        <Field label="Краткое содержание" value={document.summary} />
      </CardSection>

      <CardSection title="Рассмотрение и исполнение">
        <Field label="Резолюция" value={document.resolution_text || "—"} />
        <Field label="Срок" value={formatDate(document.due_date)} />
        <Field
          label="Просрочка"
          value={document.is_overdue ? <span className="font-medium text-red-700 dark:text-red-300">Да</span> : "Нет"}
        />
        <Field label="Планируемый результат" value={document.planned_result_label || "—"} />
        <Field label="Примечание к планируемому результату" value={document.planned_result_note || "—"} />
        <Field label="Дата исполнения" value={formatDate(document.executed_at)} />
        <Field label="Результат исполнения" value={document.execution_result || "—"} />
        <Field label="Контрольный документ" value={document.is_control_document ? "Да" : "Нет"} />
        <Field label="Контролёр" value={document.controller_user_id ? `user #${document.controller_user_id}` : "—"} />
        <Field label="Решение контролёра" value={document.control_decision || "—"} />
        <Field label="Комментарий контролёра" value={document.control_comment || "—"} />
        <Field label="Приоритет" value={document.priority_level || "—"} />
      </CardSection>

      <CardSection title="Завершение и служебные сведения">
        <Field label="Закрыто" value={formatDate(document.closed_at, true)} />
        <Field label="Передано" value={formatDate(document.transferred_at, true)} />
        <Field label="Комментарий передачи" value={document.transfer_comment || "—"} />
        <Field label="Отменено" value={formatDate(document.cancelled_at, true)} />
        <Field label="Причина отмены" value={document.cancellation_reason || "—"} />
        <Field label="Возобновлено" value={formatDate(document.reopened_at, true)} />
        <Field label="Причина возобновления" value={document.reopen_reason || "—"} />
        <Field label="Количество возобновлений" value={document.reopen_count} />
        <Field label="Исключение даты поступления" value={document.received_after_registration_exception ? "Да" : "Нет"} />
        <Field label="Комментарий исключения" value={document.exception_comment || "—"} />
        <Field label="Примечание" value={document.note || "—"} />
        <Field label="Версия записи" value={document.row_version} />
        <Field label="Создано" value={formatDate(document.created_at, true)} />
        <Field label="Обновлено" value={formatDate(document.updated_at, true)} />
      </CardSection>
    </div>
  );
}

type DetailError = { kind: "forbidden" | "not-found" | "generic"; message: string } | null;

export default function IncomingDocumentDetailPageClient({ documentId }: { documentId: string }) {
  const router = useRouter();
  const parsedDocumentId = parseIncomingDocumentId(documentId);
  const [document, setDocument] = React.useState<IncomingDocumentDetail | null>(null);
  const [loading, setLoading] = React.useState(parsedDocumentId != null);
  const [error, setError] = React.useState<DetailError>(null);
  const [retryVersion, setRetryVersion] = React.useState(0);

  React.useEffect(() => {
    if (parsedDocumentId == null) {
      setDocument(null);
      setLoading(false);
      setError({ kind: "not-found", message: "Некорректный идентификатор входящего документа." });
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    void getIncomingDocument(parsedDocumentId)
      .then((body) => {
        if (!cancelled) setDocument(body);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        setDocument(null);
        const status = incomingInformationErrorStatus(caught);
        if (status === 401) {
          router.replace("/login");
          return;
        }
        if (status === 403) {
          setError({ kind: "forbidden", message: "Нет доступа к этому входящему документу." });
          return;
        }
        if (status === 404) {
          setError({ kind: "not-found", message: "Входящий документ не найден." });
          return;
        }
        setError({
          kind: "generic",
          message: incomingInformationErrorMessage(caught, "Не удалось загрузить входящий документ."),
        });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [parsedDocumentId, retryVersion, router]);

  return (
    <div className="space-y-4 p-4" data-testid="incoming-document-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Входящий документ</h1>
          {document ? <p className="mt-1 text-sm text-zinc-500">{document.registration_number}</p> : null}
        </div>
        <Link href={INCOMING_INFORMATION_NAV_HREF} className="text-sm text-blue-700 hover:underline dark:text-blue-300">
          Назад к реестру
        </Link>
      </div>

      {loading ? (
        <div className="h-32 animate-pulse rounded-xl bg-zinc-100 dark:bg-zinc-900" data-testid="incoming-document-loading" />
      ) : error?.kind === "forbidden" ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-6 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100" data-testid="incoming-document-forbidden">
          <h2 className="font-semibold">Доступ запрещён</h2>
          <p className="mt-2">{error.message}</p>
        </div>
      ) : error?.kind === "not-found" ? (
        <div className="rounded-xl border border-zinc-300 px-4 py-6 text-sm dark:border-zinc-700" data-testid="incoming-document-not-found">
          {error.message}
        </div>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200" data-testid="incoming-document-error">
          <p>{error.message}</p>
          <button type="button" onClick={() => setRetryVersion((value) => value + 1)} className="mt-3 rounded-lg border border-red-300 px-3 py-1.5 font-medium dark:border-red-800">
            Повторить
          </button>
        </div>
      ) : document ? (
        <DetailCard document={document} />
      ) : null}
    </div>
  );
}
