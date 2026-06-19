"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import HrChangeEventDrawer from "./HrChangeEventDrawer";
import { HrChangeEventsTable } from "./HrChangeEventsTable";
import CanonicalSnapshotExportButton from "./CanonicalSnapshotExportButton";
import HrChangeEventsExportButton from "./HrChangeEventsExportButton";
import {
  HR_CHANGE_EVENTS_BASE_PATH,
  HR_CHANGE_EVENT_FILTER_OPTIONS,
  hrChangeEventTypeLabel,
  buildHrChangeEventsQueryParams,
  filterHrChangeEventsBySearch,
  listHrChangeEvents,
  mapHrChangeEventsApiError,
  parseHrChangeEventsFilters,
  type HrChangeEventRow,
  type HrChangeEventsFilters,
} from "../_lib/hrChangeEventsApi.client";

function activeFilterSummary(filters: HrChangeEventsFilters): string[] {
  const parts: string[] = [];
  if (filters.source_batch_id) parts.push(`batch #${filters.source_batch_id}`);
  if (filters.new_snapshot_id) parts.push(`snapshot #${filters.new_snapshot_id}`);
  if (filters.employee_id) parts.push(`сотрудник #${filters.employee_id}`);
  if (filters.department) parts.push(`отделение «${filters.department}»`);
  if (filters.event_type) parts.push(hrChangeEventTypeLabel(filters.event_type));
  if (filters.date_from || filters.date_to) {
    parts.push(`период ${filters.date_from || "…"} — ${filters.date_to || "…"}`);
  }
  return parts;
}

export default function PersonnelHrChangeEventsPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const filters = React.useMemo(
    () => parseHrChangeEventsFilters(searchParams),
    [searchParams],
  );

  const [items, setItems] = React.useState<HrChangeEventRow[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = React.useState<HrChangeEventRow | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await listHrChangeEvents({
        ...filters,
        q: undefined,
        limit: 200,
        offset: 0,
      });
      setItems(Array.isArray(body.items) ? body.items : []);
      setTotal(Number(body.total) || 0);
    } catch (e) {
      setItems([]);
      setTotal(0);
      setError(mapHrChangeEventsApiError(e, "Не удалось загрузить изменения реестра"));
    } finally {
      setLoading(false);
    }
  }, [filters]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const filteredItems = React.useMemo(
    () => filterHrChangeEventsBySearch(items, filters.q),
    [filters.q, items],
  );

  const filterHints = activeFilterSummary(filters);

  function updateFilters(next: Partial<HrChangeEventsFilters>) {
    const merged: HrChangeEventsFilters = { ...filters, ...next };
    const params = buildHrChangeEventsQueryParams(merged);
    const qs = params.toString();
    router.replace(qs ? `${HR_CHANGE_EVENTS_BASE_PATH}?${qs}` : HR_CHANGE_EVENTS_BASE_PATH);
  }

  function clearScopedFilters() {
    router.replace(HR_CHANGE_EVENTS_BASE_PATH);
  }

  function openEvent(row: HrChangeEventRow) {
    setSelectedEvent(row);
    setDrawerOpen(true);
  }

  return (
    <div className="space-y-4 px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
            Изменения кадрового реестра
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Материализованные изменения между версиями canonical snapshot после утверждения импорта
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <HrChangeEventsExportButton filters={filters} />
          <CanonicalSnapshotExportButton includeMetadata />
        </div>
      </div>

      {filterHints.length > 0 ? (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 dark:border-blue-900/50 dark:bg-blue-950/30 dark:text-blue-100">
          <span>Активные фильтры: {filterHints.join(" · ")}</span>
          <button
            type="button"
            onClick={clearScopedFilters}
            className="rounded border border-blue-300 px-2 py-0.5 text-xs font-medium hover:bg-blue-100 dark:border-blue-800 dark:hover:bg-blue-950/50"
          >
            Сбросить
          </button>
        </div>
      ) : null}

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Тип события
          </label>
          <select
            value={filters.event_type || ""}
            onChange={(e) => updateFilters({ event_type: e.target.value || undefined })}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            {HR_CHANGE_EVENT_FILTER_OPTIONS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Отделение
          </label>
          <input
            type="text"
            value={filters.department || ""}
            onChange={(e) => updateFilters({ department: e.target.value || undefined })}
            placeholder="Точное название"
            className="min-w-[12rem] rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Дата с
          </label>
          <input
            type="date"
            value={filters.date_from || ""}
            onChange={(e) => updateFilters({ date_from: e.target.value || undefined })}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Дата по
          </label>
          <input
            type="date"
            value={filters.date_to || ""}
            onChange={(e) => updateFilters({ date_to: e.target.value || undefined })}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Поиск сотрудника
          </label>
          <input
            type="search"
            value={filters.q || ""}
            onChange={(e) => updateFilters({ q: e.target.value || undefined })}
            placeholder="ФИО, ИИН или ID"
            className="min-w-[12rem] rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          />
        </div>
        <div className="text-sm text-zinc-500 dark:text-zinc-400">
          {loading
            ? "Загрузка…"
            : filters.q?.trim()
              ? `${filteredItems.length} из ${total} событий`
              : `${total} событий`}
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
          {error}
        </div>
      ) : null}

      <HrChangeEventsTable
        items={filteredItems}
        loading={loading}
        emptyMessage={
          filterHints.length > 0
            ? "По выбранным фильтрам изменений не найдено."
            : "Изменений пока нет. События появятся после утверждения второго canonical snapshot."
        }
        onRowClick={openEvent}
      />

      <HrChangeEventDrawer
        event={selectedEvent}
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          setSelectedEvent(null);
        }}
      />
    </div>
  );
}
