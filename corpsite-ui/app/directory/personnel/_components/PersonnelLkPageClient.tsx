"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import TaskOrgFiltersBar from "@/components/TaskOrgFiltersBar";
import { useCurrentUser } from "@/lib/currentUser";
import { canHardDeleteEmployee } from "@/lib/employeeHardDelete";
import {
  bulkDeleteEmployees,
  type EmployeeBulkDeleteResponse,
} from "../../employees/_lib/api.client";
import { PERSONNEL_LK_WORKPLACE_BASE_PATH } from "../_lib/personnelApplicationsJournalNav";
import {
  buildEmployeeBulkDeleteConfirmMessage,
  formatEmployeeBulkDeleteFailureLines,
  formatEmployeeBulkDeleteSummary,
  listSelectableEmployeeIds,
} from "../_lib/personnelLkBulkDelete";
import {
  listPersonnelLkRegistry,
  mapPersonnelLkApiError,
  type PersonnelLkRegistryItem,
  type PersonnelLkRecordKind,
} from "../_lib/personnelLkApi.client";
import {
  PERSONNEL_LK_APPLICATION_STATUS_FILTER_OPTIONS,
  PERSONNEL_LK_EMPLOYEE_STATUS_FILTER_OPTIONS,
  PERSONNEL_LK_TYPE_FILTER_OPTIONS,
} from "../_lib/personnelLkLabels";
import {
  buildPersonnelLkListLoadKey,
  buildPersonnelLkRegistryHref,
  parsePersonnelLkRegistryState,
  PERSONNEL_LK_REGISTER_PARAM,
} from "../_lib/personnelLkNav";
import type { PersonnelApplicationRegisterResponse } from "../_lib/personnelApplicationsApi.client";
import PersonnelApplicationDetailDrawer from "./PersonnelApplicationDetailDrawer";
import PersonnelApplicationRegisterDrawer from "./PersonnelApplicationRegisterDrawer";
import PersonnelLkTable from "./PersonnelLkTable";

export default function PersonnelLkPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const me = useCurrentUser();
  const showBulkSelect = canHardDeleteEmployee(me);
  const filters = React.useMemo(() => parsePersonnelLkRegistryState(searchParams), [searchParams]);
  const listLoadKey = React.useMemo(() => buildPersonnelLkListLoadKey(filters), [filters]);
  const registryReturnHref = React.useMemo(
    () => buildPersonnelLkRegistryHref(filters),
    [filters],
  );

  const [items, setItems] = React.useState<PersonnelLkRegistryItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [registerOpen, setRegisterOpen] = React.useState(false);
  const [searchDraft, setSearchDraft] = React.useState(filters.q);
  const [selectedEmployeeIds, setSelectedEmployeeIds] = React.useState<Set<number>>(new Set());
  const [bulkDeleting, setBulkDeleting] = React.useState(false);
  const [bulkDeleteSummary, setBulkDeleteSummary] = React.useState<{
    summary: string;
    failures: string[];
    kind: "success" | "error";
  } | null>(null);
  const [toast, setToast] = React.useState<{ message: string; kind: "success" | "error" } | null>(
    null,
  );

  const inFlightLoadKeyRef = React.useRef<string | null>(null);
  const selectedApplicationId = filters.application_id;
  const detailOpen = selectedApplicationId != null;

  const selectableEmployeeIds = React.useMemo(
    () => listSelectableEmployeeIds(items),
    [items],
  );
  const allPageEmployeesSelected =
    selectableEmployeeIds.length > 0 &&
    selectableEmployeeIds.every((id) => selectedEmployeeIds.has(id));
  const somePageEmployeesSelected = selectableEmployeeIds.some((id) =>
    selectedEmployeeIds.has(id),
  );

  const employeeNameById = React.useMemo(() => {
    const map = new Map<number, string>();
    for (const item of items) {
      if (item.record_kind === "employee" && item.employee_id != null) {
        map.set(item.employee_id, String(item.fio || "сотрудника").trim() || "сотрудника");
      }
    }
    return map;
  }, [items]);

  React.useEffect(() => {
    setSearchDraft(filters.q);
  }, [filters.q]);

  React.useEffect(() => {
    if (searchParams.get(PERSONNEL_LK_REGISTER_PARAM) === "1") {
      setRegisterOpen(true);
    }
  }, [searchParams]);

  React.useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const clearSelection = React.useCallback(() => {
    setSelectedEmployeeIds(new Set());
  }, []);

  const loadList = React.useCallback(async () => {
    if (inFlightLoadKeyRef.current === listLoadKey) return;
    inFlightLoadKeyRef.current = listLoadKey;
    setLoading(true);
    setError(null);
    clearSelection();
    try {
      const body = await listPersonnelLkRegistry({
        q: filters.q || undefined,
        record_kind: filters.record_kind ? (filters.record_kind as PersonnelLkRecordKind) : undefined,
        status: filters.status,
        application_status: filters.application_status || undefined,
        limit: filters.limit,
        offset: filters.offset,
        org_group_id: filters.org_group_id,
        org_unit_id: filters.org_unit_id,
        position_id: filters.position_id,
      });
      setItems(Array.isArray(body.items) ? body.items : []);
      setTotal(Number(body.total) || 0);
    } catch (e) {
      setItems([]);
      setTotal(0);
      setError(mapPersonnelLkApiError(e, "Не удалось загрузить реестр личных карточек"));
    } finally {
      if (inFlightLoadKeyRef.current === listLoadKey) {
        inFlightLoadKeyRef.current = null;
      }
      setLoading(false);
    }
  }, [
    listLoadKey,
    filters.q,
    filters.record_kind,
    filters.status,
    filters.application_status,
    filters.limit,
    filters.offset,
    filters.org_group_id,
    filters.org_unit_id,
    filters.position_id,
    clearSelection,
  ]);

  React.useEffect(() => {
    void loadList();
  }, [loadList]);

  function replaceRegistryState(next: Partial<typeof filters>) {
    const merged = { ...filters, ...next };
    router.replace(buildPersonnelLkRegistryHref(merged));
  }

  function applySearch() {
    const normalized = searchDraft.trim();
    if (normalized === filters.q) return;
    replaceRegistryState({ q: normalized, offset: 0 });
  }

  function openApplicant(applicationId: number) {
    replaceRegistryState({ application_id: applicationId });
  }

  function closeApplicant() {
    replaceRegistryState({ application_id: null });
  }

  function handleRegistered(result: PersonnelApplicationRegisterResponse) {
    replaceRegistryState({ application_id: result.application_id });
    inFlightLoadKeyRef.current = null;
    void loadList();
  }

  function toggleSelectedEmployee(employeeId: number) {
    setSelectedEmployeeIds((current) => {
      const next = new Set(current);
      if (next.has(employeeId)) next.delete(employeeId);
      else next.add(employeeId);
      return next;
    });
  }

  function toggleSelectAllPageEmployees() {
    setSelectedEmployeeIds((current) => {
      const next = new Set(current);
      if (allPageEmployeesSelected) {
        for (const id of selectableEmployeeIds) next.delete(id);
      } else {
        for (const id of selectableEmployeeIds) next.add(id);
      }
      return next;
    });
  }

  function applyBulkDeleteResult(result: EmployeeBulkDeleteResponse) {
    const deletedIds = new Set(result.deleted.map((row) => row.employee_id));
    const failedIds = new Set(result.failed.map((row) => row.employee_id));

    if (deletedIds.size > 0) {
      setItems((current) =>
        current.filter(
          (row) =>
            !(row.record_kind === "employee" && row.employee_id != null && deletedIds.has(row.employee_id)),
        ),
      );
      setTotal((current) => Math.max(0, current - deletedIds.size));
    }

    setSelectedEmployeeIds(failedIds);

    const failures = formatEmployeeBulkDeleteFailureLines(result, employeeNameById);
    const summary = formatEmployeeBulkDeleteSummary(result);
    const kind = result.failed.length > 0 ? "error" : "success";
    setBulkDeleteSummary({ summary, failures, kind });
  }

  async function handleBulkDeleteEmployees() {
    const ids = Array.from(selectedEmployeeIds);
    if (ids.length === 0) return;

    const names = ids.map((id) => employeeNameById.get(id) || `ID ${id}`);
    const confirmed = window.confirm(buildEmployeeBulkDeleteConfirmMessage(names));
    if (!confirmed) return;

    setBulkDeleting(true);
    setBulkDeleteSummary(null);
    setError(null);
    try {
      const result = await bulkDeleteEmployees(ids);
      applyBulkDeleteResult(result);
    } catch (e) {
      setError(mapPersonnelLkApiError(e, "Не удалось выполнить массовое удаление."));
    } finally {
      setBulkDeleting(false);
    }
  }

  const page = Math.floor(filters.offset / filters.limit) + 1;
  const pageCount = Math.max(1, Math.ceil(total / filters.limit));

  return (
    <div className="space-y-4 p-4" data-testid="personnel-lk-page">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Личные карточки</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Общий реестр сотрудников и претендентов: одна строка на человека, карточка или заявка по
            контексту.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              inFlightLoadKeyRef.current = null;
              void loadList();
            }}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700"
            data-testid="personnel-lk-refresh"
          >
            Обновить
          </button>
          <button
            type="button"
            onClick={() => setRegisterOpen(true)}
            className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
            data-testid="personnel-lk-register-button"
          >
            Зарегистрировать претендента
          </button>
        </div>
      </div>

      <TaskOrgFiltersBar
        basePath={PERSONNEL_LK_WORKPLACE_BASE_PATH}
        className="rounded-xl border border-zinc-200 p-3 dark:border-zinc-800"
      />

      <div className="flex flex-wrap items-end gap-3">
        <label className="block min-w-[14rem] flex-1 text-sm">
          <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Поиск</span>
          <input
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            placeholder="ФИО, ИИН, № заявки"
            className="w-full rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
            onKeyDown={(e) => {
              if (e.key === "Enter") applySearch();
            }}
            onBlur={applySearch}
            data-testid="personnel-lk-search"
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Тип</span>
          <select
            value={filters.record_kind}
            onChange={(e) =>
              replaceRegistryState({
                record_kind: e.target.value as typeof filters.record_kind,
                offset: 0,
              })
            }
            className="min-w-[160px] rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
            data-testid="personnel-lk-type-filter"
          >
            {PERSONNEL_LK_TYPE_FILTER_OPTIONS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Статус сотрудника</span>
          <select
            value={filters.status}
            onChange={(e) =>
              replaceRegistryState({
                status: e.target.value as typeof filters.status,
                offset: 0,
              })
            }
            className="min-w-[180px] rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
            data-testid="personnel-lk-status-filter"
          >
            {PERSONNEL_LK_EMPLOYEE_STATUS_FILTER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Статус заявки</span>
          <select
            value={filters.application_status}
            onChange={(e) =>
              replaceRegistryState({
                application_status: e.target.value,
                offset: 0,
              })
            }
            className="min-w-[220px] rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
            data-testid="personnel-lk-application-status-filter"
          >
            {PERSONNEL_LK_APPLICATION_STATUS_FILTER_OPTIONS.map((option) => (
              <option key={option.value || "any"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {showBulkSelect && selectedEmployeeIds.size > 0 ? (
        <div
          className="flex flex-wrap items-center gap-3 rounded-xl border border-zinc-200 p-3 dark:border-zinc-800"
          data-testid="personnel-lk-bulk-panel"
        >
          <span className="text-sm text-zinc-600 dark:text-zinc-400" data-testid="personnel-lk-selected-count">
            Выбрано: {selectedEmployeeIds.size}
          </span>
          <button
            type="button"
            disabled={bulkDeleting || loading}
            onClick={() => void handleBulkDeleteEmployees()}
            className="rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="personnel-lk-bulk-delete-btn"
          >
            {bulkDeleting ? "Удаление…" : "Удалить выбранные"}
          </button>
        </div>
      ) : null}

      {bulkDeleteSummary ? (
        <div
          className={[
            "rounded-lg border px-3 py-2 text-sm",
            bulkDeleteSummary.kind === "error"
              ? "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100"
              : "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100",
          ].join(" ")}
          data-testid="personnel-lk-bulk-summary"
        >
          <p data-testid="personnel-lk-bulk-summary-text">{bulkDeleteSummary.summary}</p>
          {bulkDeleteSummary.failures.length > 0 ? (
            <ul className="mt-2 list-disc space-y-1 pl-5" data-testid="personnel-lk-bulk-failures">
              {bulkDeleteSummary.failures.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {error ? (
        <div
          className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200"
          data-testid="personnel-lk-error"
        >
          {error}
        </div>
      ) : null}

      <PersonnelLkTable
        items={items}
        loading={loading}
        registryReturnHref={registryReturnHref}
        onOpenApplicant={openApplicant}
        showBulkSelect={showBulkSelect}
        selectedEmployeeIds={selectedEmployeeIds}
        onToggleEmployee={toggleSelectedEmployee}
        onToggleSelectAllPage={toggleSelectAllPageEmployees}
        allPageEmployeesSelected={allPageEmployeesSelected}
        somePageEmployeesSelected={somePageEmployeesSelected}
      />

      {!loading && !error ? (
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-zinc-600 dark:text-zinc-400">
          <span data-testid="personnel-lk-total">
            Всего: {total} · страница {page} из {pageCount}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={filters.offset <= 0 || loading}
              onClick={() =>
                replaceRegistryState({ offset: Math.max(0, filters.offset - filters.limit) })
              }
              className="rounded-lg border border-zinc-300 px-3 py-1.5 disabled:opacity-50 dark:border-zinc-700"
              data-testid="personnel-lk-page-prev"
            >
              Назад
            </button>
            <button
              type="button"
              disabled={filters.offset + filters.limit >= total || loading}
              onClick={() => replaceRegistryState({ offset: filters.offset + filters.limit })}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 disabled:opacity-50 dark:border-zinc-700"
              data-testid="personnel-lk-page-next"
            >
              Вперёд
            </button>
          </div>
        </div>
      ) : null}

      {toast ? (
        <div
          role="status"
          className={[
            "fixed bottom-4 right-4 z-[60] rounded-lg px-4 py-2 text-sm shadow-lg",
            toast.kind === "error" ? "bg-red-700 text-white" : "bg-emerald-700 text-white",
          ].join(" ")}
          data-testid="personnel-lk-toast"
        >
          {toast.message}
        </div>
      ) : null}

      <PersonnelApplicationRegisterDrawer
        open={registerOpen}
        onClose={() => setRegisterOpen(false)}
        onRegistered={handleRegistered}
        onToast={(message, kind = "success") => setToast({ message, kind })}
      />

      <PersonnelApplicationDetailDrawer
        applicationId={selectedApplicationId}
        open={detailOpen}
        journalReturnHref={registryReturnHref}
        onClose={closeApplicant}
        onDetailChanged={() => {
          inFlightLoadKeyRef.current = null;
          void loadList();
        }}
      />
    </div>
  );
}
