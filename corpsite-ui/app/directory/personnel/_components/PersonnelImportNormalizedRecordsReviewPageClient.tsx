"use client";

import * as React from "react";

import ImportDiffStatusBadge from "./ImportDiffStatusBadge";
import ImportFieldDiffPanel from "./ImportFieldDiffPanel";
import ImportNormalizedRecordDrawer from "./ImportNormalizedRecordDrawer";
import ImportMonthlyDiffSummaryPanel from "./ImportMonthlyDiffSummaryPanel";
import NormalizedRecordsPromotionPanel from "./NormalizedRecordsPromotionPanel";
import {
  EMPLOYEE_BINDING_STATUS_LABELS,
  employeeBindingBadgeClass,
  getNormalizedRecordsSummary,
  listImportBatches,
  listNormalizedRecords,
  mapImportApiError,
  NORMALIZED_RECORD_KIND_LABELS,
  NORMALIZED_RECORD_KINDS,
  NORMALIZED_RECORD_KIND_SUMMARY_LABELS,
  NORMALIZED_REVIEW_STATUS_LABELS,
  repairBatchEmployeeBindings,
  type ImportBatchRow,
  type NormalizedRecord,
  type NormalizedRecordKind,
  type NormalizedRecordReviewStatus,
  type NormalizedRecordSummary,
} from "../_lib/importApi.client";

export const PERSONNEL_IMPORT_NORMALIZED_REVIEW_UI_PHASE = "3g-employee-binding";

const REVIEW_HELP_EXPANDED_STORAGE_KEY = "corpsite_personnel_import_normalized_review_help_expanded";

function RowOpenHint() {
  return (
    <span
      className="inline-flex items-center gap-1 text-xs text-zinc-400 transition group-hover:text-blue-600 dark:group-hover:text-blue-400"
      aria-hidden="true"
    >
      <svg
        className="h-4 w-4 shrink-0 opacity-60 transition group-hover:opacity-100"
        viewBox="0 0 20 20"
        fill="currentColor"
      >
        <path
          fillRule="evenodd"
          d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
          clipRule="evenodd"
        />
      </svg>
      <span className="whitespace-nowrap">Нажмите для просмотра</span>
    </span>
  );
}

function NormalizedRecordsReviewHelpPanel({ onCollapse }: { onCollapse: () => void }) {
  return (
    <div
      className="mt-3 rounded-xl border border-blue-200 bg-blue-50/80 px-4 py-4 text-sm text-zinc-700 dark:border-blue-900/50 dark:bg-blue-950/30 dark:text-zinc-300"
      data-help-panel="normalized-records-review"
      data-help-visible="true"
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
          Проверка нормализованных записей
        </h2>
        <button
          type="button"
          onClick={onCollapse}
          className="relative z-10 shrink-0 rounded border border-zinc-300 px-2 py-1 text-xs text-zinc-600 hover:bg-white dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900"
        >
          Свернуть
        </button>
      </div>

      <p className="leading-relaxed">
        Система автоматически преобразует данные кадрового импорта в структурированные записи:
      </p>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        <li>Образование</li>
        <li>Обучение</li>
        <li>Сертификаты</li>
        <li>Категории</li>
      </ul>
      <p className="mt-3 leading-relaxed">
        Все записи на этой странице являются результатом автоматического анализа импортированных данных
        и требуют проверки ответственным сотрудником.
      </p>

      <p className="mt-4 font-medium text-zinc-900 dark:text-zinc-100">Порядок работы:</p>
      <ol className="mt-2 list-decimal space-y-1 pl-5">
        <li>Нажмите на строку записи.</li>
        <li>В открывшейся карточке проверьте данные.</li>
        <li>Сверьте запись с кадровыми документами сотрудника.</li>
        <li>При корректных данных нажмите «Утвердить».</li>
        <li>При ошибке нажмите «Отклонить».</li>
        <li>Если требуется повторная проверка — «Вернуть в ожидание».</li>
        <li>После утверждения записей выберите импорт и выполните Dry Run promotion.</li>
        <li>Если dry-run успешен — подтвердите Promote для записи в кадровую карточку.</li>
      </ol>

      <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-amber-950 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100">
        <p className="font-medium">Важно:</p>
        <p className="mt-1 leading-relaxed">
          Утверждение на этом этапе НЕ записывает данные в кадровую карточку сотрудника. Для записи
          используйте блок Promotion: сначала Dry Run, затем Promote с подтверждением.
        </p>
      </div>
    </div>
  );
}

function reviewStatusBadgeClass(status: NormalizedRecordReviewStatus): string {
  switch (status) {
    case "pending":
      return "border-amber-200 bg-amber-100 text-amber-900 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-200";
    case "approved":
      return "border-green-200 bg-green-100 text-green-900 dark:border-green-800 dark:bg-green-950/50 dark:text-green-200";
    case "rejected":
      return "border-red-200 bg-red-100 text-red-900 dark:border-red-800 dark:bg-red-950/50 dark:text-red-200";
    case "promoted":
      return "border-blue-200 bg-blue-100 text-blue-900 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-200";
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
  const [bindingStatus, setBindingStatus] = React.useState("");
  const [showUnchanged, setShowUnchanged] = React.useState(false);
  const [offset, setOffset] = React.useState(0);
  const [repairing, setRepairing] = React.useState(false);
  const limit = 50;

  const [selected, setSelected] = React.useState<NormalizedRecord | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [toast, setToast] = React.useState<ToastState>(null);
  const [isHelpExpanded, setIsHelpExpanded] = React.useState(true);
  const [helpStorageReady, setHelpStorageReady] = React.useState(false);

  React.useEffect(() => {
    try {
      const stored = window.localStorage.getItem(REVIEW_HELP_EXPANDED_STORAGE_KEY);
      if (stored === "false") {
        setIsHelpExpanded(false);
      }
    } catch {
      // ignore private mode / quota
    }
    setHelpStorageReady(true);
  }, []);

  React.useEffect(() => {
    if (!helpStorageReady) return;
    try {
      window.localStorage.setItem(REVIEW_HELP_EXPANDED_STORAGE_KEY, isHelpExpanded ? "true" : "false");
    } catch {
      // ignore private mode / quota
    }
  }, [isHelpExpanded, helpStorageReady]);

  React.useEffect(() => {
    listImportBatches({ withNormalizedRecords: true })
      .then((data) => setBatches(data.items))
      .catch(() => setBatches([]));
  }, []);

  const selectableBatches = React.useMemo(
    () => batches.filter((batch) => (batch.normalized_record_count ?? 0) > 0),
    [batches]
  );

  React.useEffect(() => {
    if (!batchId) return;
    const selected = batches.find((batch) => String(batch.batch_id) === batchId);
    if (selected && (selected.normalized_record_count ?? 0) === 0) {
      setBatchId("");
      setOffset(0);
    }
  }, [batches, batchId]);

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
      binding_status: bindingStatus ? (bindingStatus as "bound" | "unbound" | "conflict") : undefined,
      hide_unchanged: batchId ? !showUnchanged : undefined,
      limit,
      offset,
    }),
    [batchId, reviewStatus, recordKind, nameQuery, bindingStatus, showUnchanged, offset]
  );

  React.useEffect(() => {
    setOffset(0);
  }, [batchId, reviewStatus, recordKind, nameQuery, bindingStatus, showUnchanged]);

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

  function handlePromotionCompleted() {
    loadSummary();
    loadList();
  }

  function showToast(message: string, kind: "success" | "error" = "success") {
    setToast({ message, kind });
  }

  async function handleRepairBindings() {
    if (!batchId) {
      showToast("Выберите импорт для восстановления привязок", "error");
      return;
    }
    setRepairing(true);
    try {
      const result = await repairBatchEmployeeBindings(Number(batchId));
      showToast(
        `Привязки восстановлены: +${result.bound}, уже было ${result.already_bound}, конфликтов ${result.conflict}`,
        "success"
      );
      loadSummary();
      loadList();
    } catch (e) {
      showToast(mapImportApiError(e), "error");
    } finally {
      setRepairing(false);
    }
  }

  const kindCards = NORMALIZED_RECORD_KINDS.map((key) => ({
    key,
    label: NORMALIZED_RECORD_KIND_SUMMARY_LABELS[key],
  }));

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
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
            Проверка нормализованных записей
          </h1>
          <button
            type="button"
            onClick={() => setIsHelpExpanded((v) => !v)}
            aria-expanded={isHelpExpanded}
            className="relative z-10 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm text-blue-800 hover:bg-blue-100 dark:border-blue-900/50 dark:bg-blue-950/40 dark:text-blue-200 dark:hover:bg-blue-950/60"
          >
            Как работать с этим экраном?
          </button>
        </div>
        {isHelpExpanded ? (
          <NormalizedRecordsReviewHelpPanel onCollapse={() => setIsHelpExpanded(false)} />
        ) : null}
      </div>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>
      ) : null}

      <section className="mb-4 space-y-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <SummaryCard label="Всего" value={summary?.total ?? 0} />
          <SummaryCard label="Ожидают проверки" value={summary?.pending ?? 0} />
          <SummaryCard label="Утверждено" value={summary?.approved ?? 0} />
          <SummaryCard label="Отклонено" value={summary?.rejected ?? 0} />
          <SummaryCard label="Промотировано" value={summary?.promoted ?? 0} />
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

      <div className="mb-4 grid gap-2 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800 md:grid-cols-5">
        <select
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={batchId}
          onChange={(e) => {
            setBatchId(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">Все импорты</option>
          {selectableBatches.map((batch) => {
            const recordCount = batch.normalized_record_count ?? 0;
            return (
              <option key={batch.batch_id} value={String(batch.batch_id)}>
                {batch.file_name} (#{batch.batch_id}) — {recordCount} записей
              </option>
            );
          })}
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
        <select
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={bindingStatus}
          onChange={(e) => {
            setBindingStatus(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">Все привязки</option>
          {(Object.keys(EMPLOYEE_BINDING_STATUS_LABELS) as Array<keyof typeof EMPLOYEE_BINDING_STATUS_LABELS>).map(
            (status) => (
              <option key={status} value={status}>
                {EMPLOYEE_BINDING_STATUS_LABELS[status]}
              </option>
            )
          )}
        </select>
      </div>

      {batchId ? (
        <div className="mb-4">
          <ImportMonthlyDiffSummaryPanel
            batchId={Number(batchId)}
            showUnchanged={showUnchanged}
            onShowUnchangedChange={setShowUnchanged}
            onRecomputed={() => {
              loadSummary();
              loadList();
            }}
          />
        </div>
      ) : null}

      {batchId ? (
        <div className="mb-4">
          <button
            type="button"
            disabled={repairing || Boolean(summary?.skipped)}
            onClick={handleRepairBindings}
            className="rounded-lg border border-blue-300 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-900 hover:bg-blue-100 disabled:opacity-50 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-100"
          >
            {repairing ? "Восстановление привязок…" : "Восстановить привязки сотрудников"}
          </button>
        </div>
      ) : null}

      <NormalizedRecordsPromotionPanel
        batchId={batchId}
        recordKind={recordKind}
        tableUnavailable={Boolean(summary?.skipped)}
        onCompleted={handlePromotionCompleted}
        onToast={showToast}
      />

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
                  <th className="px-3 py-2">Diff</th>
                  <th className="px-3 py-2">Статус</th>
                  <th className="px-3 py-2">Привязка</th>
                  <th className="px-3 py-2">Тип записи</th>
                  <th className="px-3 py-2">Сотрудник</th>
                  <th className="px-3 py-2">ИИН</th>
                  <th className="px-3 py-2">Название</th>
                  <th className="px-3 py-2">Источник</th>
                  <th className="px-3 py-2">Дата создания</th>
                  <th className="px-3 py-2 w-44" aria-label="Действие" />
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="px-4 py-8 text-center text-zinc-500">
                      {batchId && !showUnchanged ? (
                        <div className="space-y-1">
                          <p className="font-medium text-zinc-700 dark:text-zinc-300">Изменений не обнаружено</p>
                          <p className="text-xs">
                            No changes detected — нормализованные записи совпадают с эталоном или нет строк по
                            фильтрам.
                          </p>
                        </div>
                      ) : (
                        "Нет записей по выбранным фильтрам"
                      )}
                    </td>
                  </tr>
                ) : (
                  items.map((row) => {
                    const rowBindingStatus =
                      row.employee_binding?.status ?? (row.employee_id ? "bound" : "unbound");
                    return (
                    <tr
                      key={row.record_id}
                      className="group cursor-pointer border-t border-zinc-100 transition hover:bg-blue-50/60 dark:border-zinc-800 dark:hover:bg-blue-950/20"
                      onClick={() => openRecord(row)}
                      title="Нажмите для просмотра"
                    >
                      <td className="px-3 py-2">
                        <ImportDiffStatusBadge status={row.diff_status} compact />
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${reviewStatusBadgeClass(row.review_status)}`}
                        >
                          {NORMALIZED_REVIEW_STATUS_LABELS[row.review_status] || row.review_status}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${employeeBindingBadgeClass(rowBindingStatus)}`}
                        >
                          {EMPLOYEE_BINDING_STATUS_LABELS[rowBindingStatus] || rowBindingStatus}
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
                      <td className="px-3 py-2 text-right">
                        <RowOpenHint />
                      </td>
                    </tr>
                    );
                  })
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
