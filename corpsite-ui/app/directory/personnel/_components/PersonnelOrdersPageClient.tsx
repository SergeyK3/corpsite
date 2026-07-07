"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import TaskOrgFiltersBar from "@/components/TaskOrgFiltersBar";

import PersonnelOrderDetailDrawer from "./PersonnelOrderDetailDrawer";
import { PersonnelOrdersTable } from "./PersonnelOrdersTable";
import {
  PERSONNEL_ORDERS_BASE_PATH,
  PERSONNEL_ORDER_STATUS_FILTER_OPTIONS,
  PERSONNEL_ORDER_TYPE_FILTER_OPTIONS,
  buildPersonnelOrdersQueryParams,
  filterPersonnelOrdersBySearch,
  listPersonnelOrders,
  mapPersonnelOrdersApiError,
  parsePersonnelOrdersFilters,
  personnelOrderStatusLabel,
  personnelOrderTypeLabel,
  type PersonnelOrderListItem,
  type PersonnelOrdersFilters,
} from "../_lib/personnelOrdersApi.client";

function activeFilterSummary(filters: PersonnelOrdersFilters): string[] {
  const parts: string[] = [];
  if (filters.employee_id) parts.push(`сотрудник #${filters.employee_id}`);
  if (filters.org_unit_id) parts.push(`подразделение #${filters.org_unit_id}`);
  if (filters.status) parts.push(personnelOrderStatusLabel(filters.status));
  if (filters.order_type_code) parts.push(personnelOrderTypeLabel(filters.order_type_code));
  if (filters.date_from || filters.date_to) {
    parts.push(`период ${filters.date_from || "…"} — ${filters.date_to || "…"}`);
  }
  if (filters.q?.trim()) parts.push(`поиск «${filters.q.trim()}»`);
  return parts;
}

export default function PersonnelOrdersPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const filters = React.useMemo(
    () => parsePersonnelOrdersFilters(searchParams),
    [searchParams],
  );

  const [items, setItems] = React.useState<PersonnelOrderListItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [selectedOrderId, setSelectedOrderId] = React.useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await listPersonnelOrders({
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
      setError(mapPersonnelOrdersApiError(e, "Не удалось загрузить журнал приказов"));
    } finally {
      setLoading(false);
    }
  }, [filters]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const filteredItems = React.useMemo(
    () => filterPersonnelOrdersBySearch(items, filters.q),
    [filters.q, items],
  );

  const filterHints = activeFilterSummary(filters);

  function updateFilters(next: Partial<PersonnelOrdersFilters>) {
    const merged: PersonnelOrdersFilters = { ...filters, ...next };
    const params = buildPersonnelOrdersQueryParams(merged);
    const qs = params.toString();
    router.replace(qs ? `${PERSONNEL_ORDERS_BASE_PATH}?${qs}` : PERSONNEL_ORDERS_BASE_PATH);
  }

  function clearScopedFilters() {
    router.replace(PERSONNEL_ORDERS_BASE_PATH);
  }

  function openOrder(row: PersonnelOrderListItem) {
    setSelectedOrderId(row.order_id);
    setDrawerOpen(true);
  }

  return (
    <div className="space-y-4 px-4 py-3">
      <div>
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Кадровые приказы</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Журнал приказов организации — просмотр заголовков, пунктов и связанных событий
        </p>
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

      <TaskOrgFiltersBar
        basePath={PERSONNEL_ORDERS_BASE_PATH}
        className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40"
      />

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Статус
          </label>
          <select
            value={filters.status || ""}
            onChange={(e) => updateFilters({ status: e.target.value || undefined })}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            {PERSONNEL_ORDER_STATUS_FILTER_OPTIONS.map((option) => (
              <option key={option.value || "all-status"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Тип приказа
          </label>
          <select
            value={filters.order_type_code || ""}
            onChange={(e) => updateFilters({ order_type_code: e.target.value || undefined })}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            {PERSONNEL_ORDER_TYPE_FILTER_OPTIONS.map((option) => (
              <option key={option.value || "all-type"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
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
            ID сотрудника
          </label>
          <input
            type="number"
            min={1}
            value={filters.employee_id ?? ""}
            onChange={(e) => {
              const raw = e.target.value.trim();
              updateFilters({
                employee_id: raw ? Number(raw) : undefined,
              });
            }}
            placeholder="employee_id"
            className="min-w-[8rem] rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Поиск
          </label>
          <input
            type="search"
            value={filters.q || ""}
            onChange={(e) => updateFilters({ q: e.target.value || undefined })}
            placeholder="№ приказа, ФИО"
            className="min-w-[12rem] rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          />
        </div>
        <div className="text-sm text-zinc-500 dark:text-zinc-400">
          {loading
            ? "Загрузка…"
            : filters.q?.trim()
              ? `${filteredItems.length} из ${total} приказов`
              : `${total} приказов`}
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
          {error}
        </div>
      ) : null}

      <PersonnelOrdersTable
        items={filteredItems}
        loading={loading}
        emptyMessage={
          filterHints.length > 0
            ? "По выбранным фильтрам приказы не найдены."
            : "Приказы пока не зарегистрированы."
        }
        onRowClick={openOrder}
      />

      <PersonnelOrderDetailDrawer
        orderId={selectedOrderId}
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          setSelectedOrderId(null);
        }}
      />
    </div>
  );
}
