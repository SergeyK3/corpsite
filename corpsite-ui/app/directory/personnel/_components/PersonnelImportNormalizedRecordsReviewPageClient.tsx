"use client";

import * as React from "react";

import ImportNormalizedRecordDrawer from "./ImportNormalizedRecordDrawer";
import {
  getNormalizedRecordsSummary,
  listImportBatches,
  listNormalizedRecords,
  mapImportApiError,
  NORMALIZED_RECORD_KIND_LABELS,
  NORMALIZED_REVIEW_STATUS_LABELS,
  type ImportBatchRow,
  type NormalizedRecord,
  type NormalizedRecordKind,
  type NormalizedRecordReviewStatus,
  type NormalizedRecordSummary,
} from "../_lib/importApi.client";

export const PERSONNEL_IMPORT_NORMALIZED_REVIEW_UI_PHASE = "3e-normalized-records-review";

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

function formatCreatedAt(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{value}</div>
    </div>
  );
}

type ToastState = { message: string; kind: "success" | "error" } | null;

export default function PersonnelImportNormalizedRecordsReviewPageClient() {
  const [loading, setLoading] = React.useState(true);
  const [summaryLoading, setSummaryLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [summary, setSummary] = React.useState<NormalizedRecordSummary | null>(null);
  const [items, setItems] = React.useState<NormalizedRecord[]>([]);
  const [total, setTotal] = React.useState(0);
  const [batches, setBatches] = React.useState<ImportBatchRow[]>([]);
  const [batchId, setBatchId] = React.useState("");
  const [reviewStatus, setReviewStatus] = React.useState("");
  const [recordKind, setRecordKind] = React.useState("");
  const [nameQuery, setNameQuery] = React.useState("");
  const [offset, setOffset] = React.useState(0);
  const limit = 50;

  const [selected, setSelected] = React.useState<NormalizedRecord | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [toast, setToast] = React.useState<ToastState>(null);

  React.useEffect(() => {
    listImportBatches()
      .then((data) => setBatches(data.items))
      .catch(() => setBatches([]));
  }, []);

  React.useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const listParams = React.useMemo(
    () => ({
      batch_id: batchId ? Number(batchId) : undefined,
      review_status: reviewStatus ? (reviewStatus as NormalizedRecordReviewStatus) : undefined,
      record_kind: recordKind ? (recordKind as NormalizedRecordKind) : undefined,
      q_name: nameQuery.trim() || undefined,
      limit,
      offset,
    }),
    [batchId, reviewStatus, recordKind, nameQuery, offset]
  );

  const loadSummary = React.useCallback(async () => {
    setSummaryLoading(true);
    try {
      const data = await getNormalizedRecordsSummary(listParams.batch_id);
      setSummary(data);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setSummaryLoading(false);
    }
  }, [listParams.batch_id]);

  const loadList = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await listNormalizedRecords(listParams);
      setItems(data.items);
      setTotal(data.total);
      setError(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setLoading(false);
    }
  }, [listParams]);

  React.useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  React.useEffect(() => {
    loadList();
  }, [loadList]);

  function openRecord(record: NormalizedRecord) {
    setSelected(record);
    setDrawerOpen(true);
  }

  function handleReviewed(updated: NormalizedRecord) {
    setItems((prev) => prev.map((item) => (item.record_id === updated.record_id ? updated : item)));
    setSelected(updated);
    loadSummary();
  }

  function showToast(message: string, kind: "success" | "error" = "success") {
    setToast({ message, kind });
  }

  const kindCards: { key: NormalizedRecordKind; label: string }[] = [
    { key: "training", label: "Обучение" },
    { key: "certificate", label: "Сертификаты" },
    { key: "category", label: "Категории" },
    { key: "education", label: "Награды" },
  ];

  return (
    <div className="px-4 py-3" data-ui-phase={PERSONNEL_IMPORT_NORMALIZED_REVIEW_UI_PHASE}>
      {toast ? (
        <div
          className={`fixed bottom-4 right-4 z-[60] max-w-sm rounded-lg border px-4 py-3 text-sm shadow-lg ${
            toast.kind === "success"
              ? "border-green-200 bg-green-50 text-green-900"
              : "border-red-200 bg-red-50 text-red-900"
          }`}
        >
          {toast.message}
        </div>
      ) : null}

      <div className="mb-4">
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
          Проверка нормализованных записей
        </h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Staging-слой перед промотированием в реестр документов. Утверждение не записывает данные в кадровую карточку.
        </p>
      </div>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      ) : null}

      <section className="mb-4 space-y-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <SummaryCard label="Всего" value={summary?.total ?? 0} />
          <SummaryCard label="Ожидают проверки" value={summary?.pending ?? 0} />
          <SummaryCard label="Утверждено" value={summary?.approved ?? 0} />
          <SummaryCard label="Отклонено" value={summary?.rejected ?? 0} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {kindCards.map((card) => (
            <SummaryCard
              key={card.key}
              label={card.label}
              value={summary?.by_kind?.[card.key] ?? 0}
            />
          ))}
        </div>
        {summaryLoading ? <div className="text-xs text-zinc-500">Обновление сводки…</div> : null}
        {summary?.skipped ? (
          <div className="text-sm text-amber-700">
            Таблица нормализованных записей недоступна — примените миграцию ADR-039 Phase 3B.
          </div>
        ) : null}
      </section>

      <div className="mb-4 grid gap-2 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800 md:grid-cols-4">
        <select
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={batchId}
          onChange={(e) => {
            setBatchId(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">Все импорты</option>
          {batches.map((batch) => (
            <option key={batch.batch_id} value={batch.batch_id}>
              {batch.file_name} (#{batch.batch_id})
            </option>
          ))}
        </select>
        <select
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={reviewStatus}
          onChange={(e) => {
            setReviewStatus(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">Все статусы</option>
          {(Object.keys(NORMALIZED_REVIEW_STATUS_LABELS) as NormalizedRecordReviewStatus[]).map((status) => (
            <option key={status} value={status}>
              {NORMALIZED_REVIEW_STATUS_LABELS[status]}
            </option>
          ))}
        </select>
        <select
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={recordKind}
          onChange={(e) => {
            setRecordKind(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">Все типы</option>
          {(Object.keys(NORMALIZED_RECORD_KIND_LABELS) as NormalizedRecordKind[]).map((kind) => (
            <option key={kind} value={kind}>
              {NORMALIZED_RECORD_KIND_LABELS[kind]}
            </option>
          ))}
        </select>
        <input
          type="search"
          placeholder="Поиск по ФИО сотрудника"
          value={nameQuery}
          onChange={(e) => {
            setNameQuery(e.target.value);
            setOffset(0);
          }}
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
        />
      </div>

      <section className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
        <div className="border-b border-zinc-200 px-4 py-3 text-sm font-semibold dark:border-zinc-800">
          Записи ({total})
        </div>
        {loading ? (
          <div className="py-12 text-center text-zinc-500">Загрузка…</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-zinc-50 text-left text-[11px] uppercase text-zinc-500 dark:bg-zinc-900">
                <tr>
                  <th className="px-3 py-2">Статус</th>
                  <th className="px-3 py-2">Тип записи</th>
                  <th className="px-3 py-2">Сотрудник</th>
                  <th className="px-3 py-2">ИИН</th>
                  <th className="px-3 py-2">Название</th>
                  <th className="px-3 py-2">Источник</th>
                  <th className="px-3 py-2">Дата создания</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-zinc-500">
                      Нет записей по выбранным фильтрам
                    </td>
                  </tr>
                ) : (
                  items.map((row) => (
                    <tr
                      key={row.record_id}
                      className="cursor-pointer border-t border-zinc-100 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900/50"
                      onClick={() => openRecord(row)}
                    >
                      <td className="px-3 py-2">
                        <span
                          className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${reviewStatusBadgeClass(row.review_status)}`}
                        >
                          {NORMALIZED_REVIEW_STATUS_LABELS[row.review_status] || row.review_status}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        {NORMALIZED_RECORD_KIND_LABELS[row.record_kind] || row.record_kind}
                      </td>
                      <td className="px-3 py-2 font-medium">{row.full_name || "—"}</td>
                      <td className="px-3 py-2">{row.iin_masked || "—"}</td>
                      <td className="px-3 py-2 max-w-[220px] truncate">{row.title || row.source_text || "—"}</td>
                      <td className="px-3 py-2">{row.source_field || "—"}</td>
                      <td className="px-3 py-2">{formatCreatedAt(row.created_at)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
        {total > limit ? (
          <div className="flex items-center justify-between border-t border-zinc-200 px-4 py-3 text-sm dark:border-zinc-800">
            <span className="text-zinc-500">
              {offset + 1}–{Math.min(offset + limit, total)} из {total}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={offset === 0}
                onClick={() => setOffset((v) => Math.max(0, v - limit))}
                className="rounded border border-zinc-300 px-3 py-1 disabled:opacity-40 dark:border-zinc-700"
              >
                Назад
              </button>
              <button
                type="button"
                disabled={offset + limit >= total}
                onClick={() => setOffset((v) => v + limit)}
                className="rounded border border-zinc-300 px-3 py-1 disabled:opacity-40 dark:border-zinc-700"
              >
                Далее
              </button>
            </div>
          </div>
        ) : null}
      </section>

      <ImportNormalizedRecordDrawer
        record={selected}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onReviewed={handleReviewed}
        onToast={showToast}
      />
    </div>
  );
}
