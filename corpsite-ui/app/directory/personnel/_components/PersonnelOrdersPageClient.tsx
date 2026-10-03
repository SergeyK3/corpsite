"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCurrentUser } from "@/lib/currentUser";

import TaskOrgFiltersBar from "@/components/TaskOrgFiltersBar";
import { getEmployees } from "@/app/directory/employees/_lib/api.client";
import { mapEmployeesResponseToSearchOptions, type EmployeeSearchOption } from "../_lib/personnelOrderEmployeeSearch";

import PersonnelOrderCreateDialog from "./PersonnelOrderCreateDialog";
import PersonnelOrderDetailDrawer from "./PersonnelOrderDetailDrawer";
import { PersonnelOrdersTable } from "./PersonnelOrdersTable";
import {
  PERSONNEL_ORDERS_BASE_PATH,
  PERSONNEL_ORDER_STATUS_FILTER_OPTIONS,
  PERSONNEL_ORDER_TYPE_FILTER_OPTIONS,
  buildPersonnelOrdersQueryParams,
  filterPersonnelOrdersBySearch,
  listPersonnelOrders,
  deletePersonnelOrderAsHrHead,
  mapPersonnelOrdersApiError,
  parsePersonnelOrdersFilters,
  personnelOrderStatusLabel,
  personnelOrderTypeLabel,
  type PersonnelOrderManualDraftCreateResult,
  type PersonnelOrderListItem,
  type PersonnelOrdersFilters,
} from "../_lib/personnelOrdersApi.client";

function activeFilterSummary(filters: PersonnelOrdersFilters): string[] {
  const parts: string[] = [];
  if (filters.order_id) parts.push(`приказ #${filters.order_id}`);
  if (filters.employee_id) parts.push("сотрудник");
  if (filters.org_unit_id) parts.push(`подразделение #${filters.org_unit_id}`);
  if (filters.status) parts.push(personnelOrderStatusLabel(filters.status));
  if (filters.order_type_code) parts.push(personnelOrderTypeLabel(filters.order_type_code));
  if (filters.date_from || filters.date_to) {
    parts.push(`период ${filters.date_from || "…"} — ${filters.date_to || "…"}`);
  }
  if (filters.q?.trim()) parts.push(`поиск «${filters.q.trim()}»`);
  if (filters.include_closed) parts.push("включая закрытые документы");
  return parts;
}

export default function PersonnelOrdersPageClient() {
  const me = useCurrentUser();
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnTo = React.useMemo(() => {
    const raw = searchParams.get("return_to");
    return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : null;
  }, [searchParams]);

  const filters = React.useMemo(
    () => parsePersonnelOrdersFilters(searchParams),
    [searchParams],
  );

  const hirePersonId = React.useMemo(() => {
    const raw = searchParams.get("hire_person_id");
    const numeric = Number(raw);
    return Number.isFinite(numeric) && numeric > 0 ? numeric : null;
  }, [searchParams]);
  // `items` is the previous deep-link value for the document correction tab.
  // The drawer resolves it to Corrections for REGISTERED/SIGNED and to Data
  // for all other states after loading the order.
  const requestedDrawerTab = searchParams.get("tab");
  const drawerInitialTab = requestedDrawerTab === "data" || requestedDrawerTab === "items"
    ? requestedDrawerTab
    : undefined;

  const [items, setItems] = React.useState<PersonnelOrderListItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [selectedOrderId, setSelectedOrderId] = React.useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [toast, setToast] = React.useState<string | null>(null);
  const [employeeQuery, setEmployeeQuery] = React.useState("");
  const [employeeOptions, setEmployeeOptions] = React.useState<EmployeeSearchOption[]>([]);

  React.useEffect(() => {
    const query = employeeQuery.trim();
    if (query.length < 2) { setEmployeeOptions([]); return; }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void getEmployees({ q: query, limit: 20, status: "all" }).then((response) => {
        if (!cancelled) setEmployeeOptions(mapEmployeesResponseToSearchOptions(response));
      }).catch(() => { if (!cancelled) setEmployeeOptions([]); });
    }, 200);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [employeeQuery]);

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await listPersonnelOrders({
        ...filters,
        order_id: undefined,
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

  React.useEffect(() => {
    if (filters.order_id && filters.order_id > 0) {
      setSelectedOrderId(filters.order_id);
      setDrawerOpen(true);
    }
  }, [filters.order_id]);

  React.useEffect(() => {
    if (searchParams.get("create") === "1") {
      setCreateOpen(true);
    }
  }, [searchParams]);

  const filteredItems = React.useMemo(
    () => filterPersonnelOrdersBySearch(items, filters.q),
    [filters.q, items],
  );

  const filterHints = activeFilterSummary(filters);

  function updateFilters(next: Partial<PersonnelOrdersFilters>) {
    const merged: PersonnelOrdersFilters = { ...filters, ...next };
    const params = buildPersonnelOrdersQueryParams(merged, { includeOrderIdInQuery: true });
    const qs = params.toString();
    router.replace(qs ? `${PERSONNEL_ORDERS_BASE_PATH}?${qs}` : PERSONNEL_ORDERS_BASE_PATH);
  }

  function clearScopedFilters() {
    router.replace(PERSONNEL_ORDERS_BASE_PATH);
  }

  function openOrder(row: PersonnelOrderListItem) {
    setSelectedOrderId(row.order_id);
    setDrawerOpen(true);
    updateFilters({ order_id: row.order_id });
  }

  function closeDrawer() {
    setDrawerOpen(false);
    setSelectedOrderId(null);
    if (returnTo) {
      router.replace(returnTo);
      return;
    }
    if (filters.order_id) {
      const { order_id: _removed, ...rest } = filters;
      updateFilters({ ...rest, order_id: undefined });
    }
  }

  function handleCreated(detail: PersonnelOrderManualDraftCreateResult) {
    setToast(`Создан черновик приказа #${detail.order_id}`);
    void load();
    setSelectedOrderId(detail.order_id);
    setDrawerOpen(true);
    updateFilters({ order_id: detail.order_id });
  }

  function handleChanged() {
    void load();
  }

  async function deleteOrderAsHrHead(row: PersonnelOrderListItem) {
    if (!window.confirm(`Удалить приказ ${row.order_number || `#${row.order_id}`}?`)) return;
    try {
      const result = await deletePersonnelOrderAsHrHead(row.order_id);
      setToast(result.status === "ALREADY_DELETED" ? "Приказ уже удалён." : "Приказ удалён из рабочего контура.");
      setItems((current) => current.filter((item) => item.order_id !== row.order_id));
      setTotal((current) => Math.max(0, current - 1));
      void load();
    } catch (e) {
      setError(mapPersonnelOrdersApiError(e, "Не удалось удалить приказ."));
    }
  }

  return (
    <div className="space-y-4 px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Кадровые приказы</h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Журнал приказов: создание черновиков, регистрация и применение кадровых изменений
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          className="rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
          data-testid="personnel-order-create-button"
        >
          Создать приказ
        </button>
      </div>

      {toast ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900 dark:border-emerald-900/55 dark:bg-emerald-950/35 dark:text-emerald-100">
          {toast}
        </div>
      ) : null}

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
            Качество записи
          </label>
          <select
            data-testid="personnel-orders-reconstruction-quality"
            value={filters.record_quality || "WORKING"}
            onChange={(e) => updateFilters({ record_quality: e.target.value as PersonnelOrdersFilters["record_quality"] })}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            <option value="WORKING">Рабочие записи</option>
            <option value="TECHNICAL">Технические записи</option>
            <option value="ALL">Все записи</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Реконструкция
          </label>
          <select
            value={filters.reconstruction_quality || ""}
            onChange={(e) => updateFilters({ reconstruction_quality: e.target.value as PersonnelOrdersFilters["reconstruction_quality"] || undefined })}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            <option value="">Все</option>
            <option value="NEEDS_DOCX_REVIEW">Требуют сверки с DOCX</option>
            <option value="RECONSTRUCTED_PILOT">Восстановленные из журнала</option>
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
        <div className="relative">
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Сотрудник
          </label>
          <input
            type="search"
            aria-label="Сотрудник"
            value={employeeQuery}
            onChange={(e) => setEmployeeQuery(e.target.value)}
            placeholder="Введите фамилию или ФИО"
            className="min-w-[14rem] rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          />
          {filters.employee_id ? <button type="button" aria-label="Очистить сотрудника" onClick={() => { setEmployeeQuery(""); updateFilters({ employee_id: undefined }); }} className="ml-2 text-xs underline">Очистить</button> : null}
          {employeeOptions.length > 0 ? <div className="absolute z-20 mt-1 w-full rounded border bg-white shadow dark:bg-zinc-950">{employeeOptions.map((option) => <button key={option.employee_id} type="button" className="block w-full px-3 py-2 text-left text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800" onClick={() => { setEmployeeQuery(option.full_name); setEmployeeOptions([]); updateFilters({ employee_id: option.employee_id }); }}><span className="block font-medium">{option.full_name}</span><span className="block text-xs text-zinc-500">{option.position_name || "—"} · {option.org_unit_name || "—"}</span></button>)}</div> : null}
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
        <label className="flex items-center gap-2 pb-2 text-sm text-zinc-700 dark:text-zinc-300">
          <input
            type="checkbox"
            data-testid="personnel-orders-include-closed"
            checked={Boolean(filters.include_closed)}
            onChange={(e) => updateFilters({ include_closed: e.target.checked || undefined })}
            className="rounded border-zinc-300 dark:border-zinc-600"
          />
          Показывать закрытые документы
        </label>
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
            : "Приказы пока не созданы."
        }
        onRowClick={openOrder}
        onDelete={["ADMIN", "HR_HEAD"].includes(String(me?.role_code || "").trim().toUpperCase()) ? deleteOrderAsHrHead : undefined}
      />

      <PersonnelOrderDetailDrawer
        orderId={selectedOrderId}
        open={drawerOpen}
        onClose={closeDrawer}
        onChanged={handleChanged}
        hirePersonId={hirePersonId}
        initialTab={drawerInitialTab}
        allowDeletedTombstone={Boolean(returnTo?.startsWith("/admin/system"))}
      />

      <PersonnelOrderCreateDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={handleCreated}
        initialEmployeeId={filters.employee_id}
        initialEmployeeQuery={filters.q}
        initialOrgUnitId={filters.org_unit_id}
      />

    </div>
  );
}
