"use client";

import * as React from "react";

import {
  NORMALIZED_RECORD_KIND_LABELS,
  NORMALIZED_REVIEW_STATUS_LABELS,
  mapImportApiError,
  patchNormalizedRecordReview,
  type NormalizedRecord,
  type NormalizedRecordReviewStatus,
} from "../_lib/importApi.client";

type Props = {
  record: NormalizedRecord | null;
  open: boolean;
  onClose: () => void;
  onReviewed: (record: NormalizedRecord) => void;
  onToast: (message: string, kind?: "success" | "error") => void;
};

function reviewStatusBadgeClass(status: NormalizedRecordReviewStatus): string {
  switch (status) {
    case "pending":
      return "border-amber-200 bg-amber-100 text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200";
    case "approved":
      return "border-green-200 bg-green-100 text-green-900 dark:border-green-800 dark:bg-green-950/50 dark:text-green-200";
    case "rejected":
      return "border-red-200 bg-red-100 text-red-900 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200";
    default:
      return "border-zinc-200 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300";
  }
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("ru-RU");
}

function FieldRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid gap-1 sm:grid-cols-[140px_1fr] sm:gap-3">
      <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="text-sm text-zinc-900 dark:text-zinc-100">{value || "—"}</div>
    </div>
  );
}

function PayloadSection({ record }: { record: NormalizedRecord }) {
  const kind = record.record_kind;

  if (kind === "training") {
    return (
      <div className="space-y-3">
        <FieldRow label="Название курса" value={record.title} />
        <FieldRow label="Организация" value={record.provider} />
        <FieldRow label="Часы" value={record.hours != null ? String(record.hours) : null} />
        <FieldRow label="Дата начала" value={formatDate(record.start_date)} />
        <FieldRow label="Дата окончания" value={formatDate(record.end_date)} />
        <FieldRow label="Дата выдачи" value={formatDate(record.issue_date)} />
        <FieldRow label="Документ" value={record.file_url ? <a href={record.file_url} className="text-blue-600 hover:underline" target="_blank" rel="noreferrer">{record.file_url}</a> : null} />
        <FieldRow label="Номер документа" value={record.document_number} />
      </div>
    );
  }

  if (kind === "certificate") {
    return (
      <div className="space-y-3">
        <FieldRow label="Название" value={record.title} />
        <FieldRow label="Организация" value={record.provider} />
        <FieldRow label="Специальность" value={record.specialty_text} />
        <FieldRow label="Дата выдачи" value={formatDate(record.issue_date)} />
        <FieldRow label="Действует до" value={formatDate(record.expiry_date)} />
        <FieldRow label="Номер документа" value={record.document_number} />
        <FieldRow label="Документ" value={record.file_url ? <a href={record.file_url} className="text-blue-600 hover:underline" target="_blank" rel="noreferrer">{record.file_url}</a> : null} />
      </div>
    );
  }

  if (kind === "category") {
    return (
      <div className="space-y-3">
        <FieldRow label="Категория" value={record.title} />
        <FieldRow label="Специальность" value={record.specialty_text} />
        <FieldRow label="Действует до" value={formatDate(record.expiry_date)} />
        <FieldRow label="Дата выдачи" value={formatDate(record.issue_date)} />
      </div>
    );
  }

  if (kind === "education") {
    return (
      <div className="space-y-3">
        <FieldRow label="Название" value={record.title} />
        <FieldRow label="Организация" value={record.provider} />
        <FieldRow label="Дата выдачи" value={formatDate(record.issue_date)} />
        <FieldRow label="Номер документа" value={record.document_number} />
        <FieldRow label="Документ" value={record.file_url ? <a href={record.file_url} className="text-blue-600 hover:underline" target="_blank" rel="noreferrer">{record.file_url}</a> : null} />
      </div>
    );
  }

  return (
    <pre className="overflow-x-auto rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs dark:border-zinc-800 dark:bg-zinc-900">
      {JSON.stringify(record, null, 2)}
    </pre>
  );
}

export default function ImportNormalizedRecordDrawer({ record, open, onClose, onReviewed, onToast }: Props) {
  const [notes, setNotes] = React.useState("");
  const [acting, setActing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) return;
    setNotes(record?.review_notes || "");
    setError(null);
  }, [open, record]);

  React.useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  async function applyStatus(target: NormalizedRecordReviewStatus) {
    if (!record) return;
    setActing(true);
    setError(null);
    try {
      const updated = await patchNormalizedRecordReview(record.record_id, {
        review_status: target,
        review_notes: target === "pending" ? undefined : notes.trim() || undefined,
      });
      onReviewed(updated);
      onToast(
        target === "approved"
          ? "Запись утверждена"
          : target === "rejected"
            ? "Запись отклонена"
            : "Запись возвращена в ожидание",
        "success"
      );
    } catch (e) {
      const message = mapImportApiError(e);
      setError(message);
      onToast(message, "error");
    } finally {
      setActing(false);
    }
  }

  if (!open || !record) return null;

  const status = record.review_status;
  const canApprove = status === "pending";
  const canReject = status === "pending";
  const canReturnPending = status === "approved" || status === "rejected";
  const locked = status === "promoted" || status === "superseded";

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-zinc-600/35 backdrop-blur-sm dark:bg-black/50" onClick={onClose} />

      <div className="relative ml-auto flex h-full w-full max-w-[720px] flex-col border-l border-zinc-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between gap-4 border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Нормализованная запись</h2>
            <p className="mt-1 text-sm text-zinc-500">ID {record.record_id} · batch {record.batch_id}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-sm text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-900"
          >
            Закрыть
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-6">
          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
          ) : null}

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Общие данные</h3>
            <FieldRow label="Сотрудник" value={record.full_name || (record.employee_id ? `ID ${record.employee_id}` : "—")} />
            <FieldRow label="ИИН" value={record.iin_masked || "—"} />
            <FieldRow
              label="Тип записи"
              value={NORMALIZED_RECORD_KIND_LABELS[record.record_kind] || record.record_kind}
            />
            <FieldRow label="Источник" value={record.source_field} />
            <FieldRow
              label="Статус"
              value={
                <span
                  className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${reviewStatusBadgeClass(status)}`}
                >
                  {NORMALIZED_REVIEW_STATUS_LABELS[status] || status}
                </span>
              }
            />
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Исходный текст</h3>
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
              {record.source_text || "—"}
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Нормализованные данные</h3>
            <PayloadSection record={record} />
            <div className="grid gap-2 text-xs text-zinc-500 sm:grid-cols-2">
              <div>Метод: {record.parse_method}</div>
              <div>Уверенность: {record.confidence != null ? record.confidence : "—"}</div>
              <div>Ключ: {record.source_record_key}</div>
              <div>Тип документа: {record.document_type_code || "—"}</div>
            </div>
          </section>

          {!locked ? (
            <section className="space-y-2">
              <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300" htmlFor="review-notes">
                Комментарий проверки
              </label>
              <textarea
                id="review-notes"
                rows={3}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                placeholder="Необязательно"
              />
            </section>
          ) : (
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
              Статус «{NORMALIZED_REVIEW_STATUS_LABELS[status]}» не может быть изменён вручную.
            </div>
          )}
        </div>

        <div className="flex flex-wrap gap-2 border-t border-zinc-200 px-5 py-4 dark:border-zinc-800">
          {canApprove ? (
            <button
              type="button"
              disabled={acting}
              onClick={() => applyStatus("approved")}
              className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              Утвердить
            </button>
          ) : null}
          {canReject ? (
            <button
              type="button"
              disabled={acting}
              onClick={() => applyStatus("rejected")}
              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              Отклонить
            </button>
          ) : null}
          {canReturnPending ? (
            <button
              type="button"
              disabled={acting}
              onClick={() => applyStatus("pending")}
              className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-900"
            >
              Вернуть в ожидание
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
