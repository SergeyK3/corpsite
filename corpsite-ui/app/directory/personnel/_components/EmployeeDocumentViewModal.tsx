// FILE: corpsite-ui/app/directory/personnel/_components/EmployeeDocumentViewModal.tsx
"use client";

import * as React from "react";

import { fmtProfileDate, expiryStatusMeta, documentExpiryStatus } from "../../employees/_lib/professionalProfile";
import type { EmployeeDocumentRow } from "../_lib/documentsApi.client";
import { archiveEmployeeDocument, isHttpUrl, mapDocumentsApiError } from "../_lib/documentsApi.client";

type Props = {
  open: boolean;
  document: EmployeeDocumentRow | null;
  onClose: () => void;
  onEdit: (row: EmployeeDocumentRow) => void;
  onArchived: () => void;
};

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-zinc-900 dark:text-zinc-100">{value || "—"}</dd>
    </div>
  );
}

export default function EmployeeDocumentViewModal({
  open,
  document: row,
  onClose,
  onEdit,
  onArchived,
}: Props) {
  const [archiving, setArchiving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) return;
    setError(null);
    setArchiving(false);
  }, [open, row?.document_id]);

  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !row) return null;

  const expiryMeta = expiryStatusMeta(documentExpiryStatus(row));
  const fileUrl = String(row.file_url || "").trim();

  async function handleArchive() {
    if (!row) return;
    if (!window.confirm("Снять документ с действия (архивировать)?")) return;
    setError(null);
    setArchiving(true);
    try {
      await archiveEmployeeDocument(row.document_id);
      onArchived();
      onClose();
    } catch (err) {
      setError(mapDocumentsApiError(err, "Не удалось архивировать документ."));
    } finally {
      setArchiving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-zinc-200 bg-white p-5 shadow-xl dark:border-zinc-800 dark:bg-zinc-950"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              Документ #{row.document_id}
            </h2>
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{row.employee_name}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-900"
          >
            ✕
          </button>
        </div>

        {error ? (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
            {error}
          </div>
        ) : null}

        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Сотрудник" value={row.employee_name} />
          <Field label="Тип документа" value={row.document_type_name} />
          <Field label="Вид документа" value={row.document_kind_name} />
          <Field label="Специальность" value={row.medical_specialty_name} />
          <div className="sm:col-span-2">
            <Field label="Название обучения / программы" value={row.training_title} />
          </div>
          {row.document_kind_code === "OTHER" && row.title ? (
            <div className="sm:col-span-2">
              <Field label="Уточнение (прочее)" value={row.title} />
            </div>
          ) : null}
          <Field label="Номер документа" value={row.document_number} />
          <div className="sm:col-span-2">
            <Field label="Кем выдан" value={row.issued_by} />
          </div>
          <Field label="Дата выдачи" value={fmtProfileDate(row.issued_at)} />
          {row.tracks_hours || row.hours != null ? (
            <Field
              label="Количество часов"
              value={row.hours != null ? `${row.hours} ч` : "—"}
            />
          ) : null}
          <Field label="Действует до" value={fmtProfileDate(row.valid_until)} />
          <Field
            label="Статус срока"
            value={
              <span className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${expiryMeta.className}`}>
                {expiryMeta.label}
              </span>
            }
          />
          <Field label="Статус записи" value={row.lifecycle_status === "ACTIVE" ? "Действует" : row.lifecycle_status} />
          <div className="sm:col-span-2">
            <Field
              label="Ссылка на файл"
              value={
                fileUrl ? (
                  isHttpUrl(fileUrl) ? (
                    <a
                      href={fileUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="break-all text-blue-600 hover:underline dark:text-blue-400"
                    >
                      {fileUrl}
                    </a>
                  ) : (
                    <span className="break-all font-mono text-xs">{fileUrl}</span>
                  )
                ) : null
              }
            />
          </div>
          {row.comment ? (
            <div className="sm:col-span-2">
              <Field label="Комментарий" value={row.comment} />
            </div>
          ) : null}
        </dl>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-zinc-200 pt-4 dark:border-zinc-800">
          <button
            type="button"
            onClick={handleArchive}
            disabled={archiving}
            className="rounded-lg border border-red-300 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:text-red-300 dark:hover:bg-red-950/30"
          >
            {archiving ? "Архивирование…" : "Снять с действия"}
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700"
            >
              Закрыть
            </button>
            <button
              type="button"
              onClick={() => onEdit(row)}
              className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-500"
            >
              Изменить
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
