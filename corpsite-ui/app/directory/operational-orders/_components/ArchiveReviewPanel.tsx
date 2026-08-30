"use client";

import * as React from "react";

import { listArchiveReview, mapOoApiError } from "../_lib/api";
import type {
  ArchiveInitialReviewState,
  ArchiveReviewOutcome,
  ArchiveReviewOutcomeFilter,
  ArchiveReviewResponse,
  ArchiveReviewRow,
} from "../_lib/types";
import ArchiveReviewDialog from "./ArchiveReviewDialog";

const PAGE_SIZE = 25;

const REVIEW_STATE_OPTIONS: Array<{ value: ArchiveInitialReviewState; label: string }> = [
  { value: "REQUISITES_PRECONFIRMED", label: "Реквизиты предварительно подтверждены" },
  { value: "NEEDS_REQUISITES", label: "Требуется уточнить номер или дату" },
  { value: "NEEDS_DOCUMENT_TYPE", label: "Требуется проверить тип документа" },
  { value: "POSSIBLE_NON_ORDER", label: "Возможно, не является приказом" },
];

const REVIEW_STATE_LABELS = Object.fromEntries(
  REVIEW_STATE_OPTIONS.map((option) => [option.value, option.label]),
) as Record<ArchiveInitialReviewState, string>;

export const REVIEW_OUTCOME_LABELS: Record<ArchiveReviewOutcome, string> = {
  CONFIRMED: "Реквизиты приказа подтверждены",
  NEEDS_CLARIFICATION: "Требуется дополнительное уточнение",
  DRAFT_ORDER: "Проект или предварительная версия приказа",
  ORDER_ANNEX: "Приложение к приказу",
  SUPPORTING_DOCUMENT: "Документ-основание или сопроводительный документ",
  DUPLICATE: "Дубль",
  NOT_AN_ORDER: "Не относится к приказам",
};

const REVIEW_OUTCOME_OPTIONS: Array<{ value: ArchiveReviewOutcomeFilter; label: string }> = [
  { value: "UNREVIEWED", label: "Не проверено" },
  { value: "NEEDS_CLARIFICATION", label: "Требуется уточнение" },
  { value: "CONFIRMED", label: "Реквизиты подтверждены" },
  { value: "DRAFT_ORDER", label: "Проект/предварительная версия" },
  { value: "ORDER_ANNEX", label: "Приложение" },
  { value: "SUPPORTING_DOCUMENT", label: "Документ-основание/сопроводительный" },
  { value: "DUPLICATE", label: "Дубль" },
  { value: "NOT_AN_ORDER", label: "Не относится к приказам" },
];

type Filters = {
  search: string;
  initialReviewState: "" | ArchiveInitialReviewState;
  reviewOutcome: "" | ArchiveReviewOutcomeFilter;
  archiveSection: string;
  onlyMissingRequisites: boolean;
  onlyDuplicateSha: boolean;
  onlyOrder298: boolean;
};

const EMPTY_FILTERS: Filters = {
  search: "",
  initialReviewState: "",
  reviewOutcome: "",
  archiveSection: "",
  onlyMissingRequisites: false,
  onlyDuplicateSha: false,
  onlyOrder298: false,
};

export default function ArchiveReviewPanel({
  canReview,
  reviewerName = "Текущий пользователь",
}: {
  canReview: boolean;
  reviewerName?: string;
}) {
  const [filters, setFilters] = React.useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = React.useState(0);
  const [data, setData] = React.useState<ArchiveReviewResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [reloadToken, setReloadToken] = React.useState(0);
  const [selectedRowId, setSelectedRowId] = React.useState<number | null>(null);
  const [notice, setNotice] = React.useState<string | null>(null);

  React.useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    listArchiveReview({
      search: filters.search.trim() || undefined,
      initial_review_state: filters.initialReviewState || undefined,
      review_outcome: filters.reviewOutcome || undefined,
      archive_section: filters.archiveSection || undefined,
      only_missing_requisites: filters.onlyMissingRequisites || undefined,
      only_duplicate_sha: filters.onlyDuplicateSha || undefined,
      only_order_298: filters.onlyOrder298 || undefined,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
      })
      .then((response) => {
        if (!active) return;
        const lastPage = Math.max(0, Math.ceil(response.total / PAGE_SIZE) - 1);
        if (page > lastPage) {
          setPage(lastPage);
          return;
        }
        setData(response);
      })
      .catch((reason) => {
        if (active) {
          setData(null);
          setError(mapOoApiError(reason, "Не удалось загрузить архив на проверке"));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [filters, page, reloadToken]);

  function updateFilters(patch: Partial<Filters>) {
    setFilters((current) => ({ ...current, ...patch }));
    setPage(0);
  }

  if (loading && data == null) {
    return (
      <div className="rounded-xl border px-4 py-8 text-center text-sm text-zinc-500" data-testid="archive-review-loading">
        Загрузка архива на проверке…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800" role="alert">
        {error}
      </div>
    );
  }

  if (!data?.batch || !data.stats) {
    return (
      <div className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-zinc-500" data-testid="archive-review-no-batch">
        Импортированный архив для проверки пока отсутствует.
      </div>
    );
  }

  const pageCount = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const duplicateRows = formatExcelRows(data.stats.duplicate_sha_excel_rows);
  const repeated298Rows = formatExcelRows(data.stats.repeated_298_excel_rows);

  return (
    <section className="min-w-0 space-y-3" aria-label="Архив на проверке">
      {notice ? <p className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800" role="status">{notice}</p> : null}
      <div className="space-y-1 text-sm" data-testid="archive-review-summary">
        <p><span className="font-medium">Исходное качество:</span> {data.stats.initial_quality.total} записей · {data.stats.initial_quality.preconfirmed} предварительно подтверждены · {data.stats.initial_quality.incomplete} с неполными или спорными исходными данными</p>
        <p><span className="font-medium">Рабочая очередь:</span> {data.stats.work_queue.pending_review} не проверено · {data.stats.work_queue.needs_clarification} требуют уточнения · {data.stats.work_queue.completed_review} завершено</p>
      </div>

      <div className="space-y-1 text-sm" data-testid="archive-review-problems">
        {duplicateRows ? <p>⚠ Одинаковый файл: Excel-строки {duplicateRows}</p> : null}
        {repeated298Rows ? <p>⚠ Повтор номера 298-ө: Excel-строки {repeated298Rows}</p> : null}
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-zinc-200 p-3 text-sm dark:border-zinc-800">
        <label className="flex min-w-[240px] flex-1 flex-col gap-1">
          <span className="text-xs text-zinc-500">Поиск</span>
          <input
            type="search"
            className="rounded-md border px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-900"
            placeholder="Имя, номер, предмет или путь"
            value={filters.search}
            onChange={(event) => updateFilters({ search: event.target.value })}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-zinc-500">Исходное состояние</span>
          <select
            aria-label="Исходное состояние"
            className="max-w-[300px] rounded-md border px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-900"
            value={filters.initialReviewState}
            onChange={(event) => updateFilters({ initialReviewState: event.target.value as Filters["initialReviewState"] })}
          >
            <option value="">Все состояния</option>
            {REVIEW_STATE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-zinc-500">Результат проверки</span>
          <select
            aria-label="Результат проверки"
            className="max-w-[300px] rounded-md border px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-900"
            value={filters.reviewOutcome}
            onChange={(event) => updateFilters({ reviewOutcome: event.target.value as Filters["reviewOutcome"] })}
          >
            <option value="">Все результаты</option>
            {REVIEW_OUTCOME_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-zinc-500">Раздел архива</span>
          <select
            aria-label="Раздел архива"
            className="max-w-[260px] rounded-md border px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-900"
            value={filters.archiveSection}
            onChange={(event) => updateFilters({ archiveSection: event.target.value })}
          >
            <option value="">Все разделы</option>
            {data.sections.map((section) => <option key={section} value={section}>{section}</option>)}
          </select>
        </label>
        <FilterCheckbox
          label="Без номера/даты"
          checked={filters.onlyMissingRequisites}
          onChange={(checked) => updateFilters({ onlyMissingRequisites: checked })}
        />
        <FilterCheckbox
          label="Дубликат файла"
          checked={filters.onlyDuplicateSha}
          onChange={(checked) => updateFilters({ onlyDuplicateSha: checked })}
        />
        <FilterCheckbox
          label="Номер 298-ө"
          checked={filters.onlyOrder298}
          onChange={(checked) => updateFilters({ onlyOrder298: checked })}
        />
        <button
          type="button"
          className="rounded-md border px-3 py-1.5 hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
          onClick={() => {
            setFilters(EMPTY_FILTERS);
            setPage(0);
          }}
        >
          Сбросить фильтры
        </button>
      </div>

      {loading ? <p className="text-xs text-zinc-500">Обновление списка…</p> : null}
      {data.items.length ? (
        <ArchiveRowsTable items={data.items} canReview={canReview} onReview={setSelectedRowId} />
      ) : (
        <div className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-zinc-500" data-testid="archive-review-empty-filter">
          По заданным фильтрам записи не найдены.
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 text-sm" aria-label="Пагинация архива">
        <span>Найдено: {data.total} · Страница {page + 1} из {pageCount}</span>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-md border px-3 py-1.5 disabled:opacity-50 dark:border-zinc-700"
            disabled={page === 0 || loading}
            onClick={() => setPage((current) => Math.max(0, current - 1))}
          >
            Назад
          </button>
          <button
            type="button"
            className="rounded-md border px-3 py-1.5 disabled:opacity-50 dark:border-zinc-700"
            disabled={page + 1 >= pageCount || loading}
            onClick={() => setPage((current) => current + 1)}
          >
            Далее
          </button>
        </div>
      </div>
      {selectedRowId != null ? (
        <ArchiveReviewDialog
          rowId={selectedRowId}
          canReview={canReview}
          reviewerName={reviewerName}
          onClose={() => setSelectedRowId(null)}
          onSaved={(saved) => {
            setData((current) => current ? {
              ...current,
              items: current.items.map((item) => item.row_id === saved.row_id ? {
                ...item,
                review_outcome: saved.review_outcome,
                reviewer_display_name: saved.reviewer_display_name,
                reviewed_at: saved.reviewed_at,
                version: saved.version,
              } : item),
            } : current);
            setSelectedRowId(null);
            setNotice(`Проверка Excel-строки ${saved.excel_row} сохранена.`);
            setReloadToken((value) => value + 1);
          }}
        />
      ) : null}
    </section>
  );
}

function FilterCheckbox({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex items-center gap-2 whitespace-nowrap py-1.5">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      {label}
    </label>
  );
}

function ArchiveRowsTable({ items, canReview, onReview }: { items: ArchiveReviewRow[]; canReview: boolean; onReview: (rowId: number) => void }) {
  return (
    <div className="w-full max-w-full overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800" data-testid="archive-review-table">
      <table className="min-w-[1900px] text-sm">
        <caption className="sr-only">Импортированный архив производственных приказов</caption>
        <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900">
          <tr>
            <th className="px-3 py-2">Excel-строка</th>
            <th className="px-3 py-2">Раздел архива</th>
            <th className="px-3 py-2">Имя файла</th>
            <th className="px-3 py-2">Исходный статус</th>
            <th className="px-3 py-2">Исходное состояние</th>
            <th className="px-3 py-2">Результат проверки</th>
            <th className="px-3 py-2">Номер</th>
            <th className="px-3 py-2">Дата</th>
            <th className="px-3 py-2">Предмет/заголовок</th>
            <th className="px-3 py-2">Относительный путь</th>
            <th className="px-3 py-2">Проблема</th>
            <th className="px-3 py-2">Официальный документ</th>
            <th className="px-3 py-2">Действие</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.row_id} className="border-t border-zinc-100 align-top dark:border-zinc-800" data-testid={`archive-review-row-${item.excel_row}`}>
              <td className="whitespace-nowrap px-3 py-2">{item.excel_row}</td>
              <td className="px-3 py-2">{item.archive_section}</td>
              <td className="px-3 py-2 font-medium">{item.file_name}</td>
              <td className="px-3 py-2">{item.source_status}</td>
              <td className="px-3 py-2">{REVIEW_STATE_LABELS[item.initial_review_state]}</td>
              <td className="min-w-[260px] px-3 py-2">
                <span>{item.review_outcome ? REVIEW_OUTCOME_LABELS[item.review_outcome] : "Не проверено"}</span>
                {item.reviewer_display_name && item.reviewed_at ? (
                  <span className="mt-1 block text-xs text-zinc-500">Проверил: {item.reviewer_display_name}, {formatReviewedAt(item.reviewed_at)}</span>
                ) : null}
              </td>
              <td className="whitespace-nowrap px-3 py-2">{item.order_number || "—"}</td>
              <td className="whitespace-nowrap px-3 py-2">{formatOrderDate(item.order_date)}</td>
              <td className="max-w-[320px] px-3 py-2">{item.subject || "—"}</td>
              <td className="max-w-[420px] break-all px-3 py-2 font-mono text-xs">{item.relative_path || "—"}</td>
              <td className="px-3 py-2">
                <div className="space-y-1 whitespace-nowrap">
                  {item.duplicate_sha ? <span className="block">⚠ Дубликат файла</span> : null}
                  {item.repeated_298 ? <span className="block">⚠ Повтор № 298-ө</span> : null}
                  {!item.duplicate_sha && !item.repeated_298 ? "—" : null}
                </div>
              </td>
              <td className="whitespace-nowrap px-3 py-2">
                {item.official_document_id ? `Документ #${item.official_document_id}` : "Не связан"}
              </td>
              <td className="whitespace-nowrap px-3 py-2">
                <button type="button" className="rounded-md border px-3 py-1.5" onClick={() => onReview(item.row_id)}>
                  {canReview ? "Проверить" : "Просмотреть"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatOrderDate(value: string | null): string {
  if (!value) return "—";
  const [year, month, day] = value.split("-");
  return year && month && day ? `${day}.${month}.${year}` : value;
}

function formatExcelRows(rows: number[]): string {
  if (!rows.length) return "";
  if (rows.length === 2 && rows[1] === rows[0] + 1) return `${rows[0]}–${rows[1]}`;
  return rows.join(", ");
}

function formatReviewedAt(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("ru-RU");
}
