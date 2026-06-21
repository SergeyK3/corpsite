// FILE: corpsite-ui/app/admin/system/_components/user-linkage-operations/OperationsItemsTable.tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchOperationsItems,
  mapUserLinkageOperationsApiError,
  type UserLinkageOperationsItemListItem,
} from "../../_lib/userLinkageOperationsApi.client";
import {
  ITEM_ACTION_OPTIONS,
  ITEM_STATUS_OPTIONS,
  itemStatusClass,
} from "../../_lib/userLinkageOperationsLabels";
import { formatDateTime } from "../../_lib/adminSystemLabels";
import ErrorBanner from "../shared/ErrorBanner";

const PAGE_SIZE = 50;

type OperationsItemsTableProps = {
  refreshToken?: number;
  initialRunFilter?: number | null;
  initialItemId?: number | null;
  onOpenItem?: (itemId: number) => void;
};

export default function OperationsItemsTable({
  refreshToken = 0,
  initialRunFilter = null,
  initialItemId = null,
  onOpenItem,
}: OperationsItemsTableProps) {
  const [items, setItems] = useState<UserLinkageOperationsItemListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    run_id: initialRunFilter ? String(initialRunFilter) : "",
    action: "",
    status: "",
    user_id: "",
    employee_id: "",
  });

  useEffect(() => {
    if (initialRunFilter) {
      setFilters((f) => ({ ...f, run_id: String(initialRunFilter) }));
      setOffset(0);
    }
  }, [initialRunFilter]);

  useEffect(() => {
    if (initialItemId && onOpenItem) {
      onOpenItem(initialItemId);
    }
  }, [initialItemId, onOpenItem]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const runId = filters.run_id ? Number(filters.run_id) : undefined;
      const userId = filters.user_id ? Number(filters.user_id) : undefined;
      const employeeId = filters.employee_id ? Number(filters.employee_id) : undefined;
      const res = await fetchOperationsItems({
        run_id: runId && !Number.isNaN(runId) ? runId : undefined,
        action: filters.action || undefined,
        status: filters.status || undefined,
        user_id: userId && !Number.isNaN(userId) ? userId : undefined,
        employee_id: employeeId && !Number.isNaN(employeeId) ? employeeId : undefined,
        limit: PAGE_SIZE,
        offset,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(mapUserLinkageOperationsApiError(err, "Не удалось загрузить items"));
    } finally {
      setLoading(false);
    }
  }, [filters.action, filters.employee_id, filters.run_id, filters.status, filters.user_id, offset]);

  useEffect(() => {
    void load();
  }, [load, refreshToken]);

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="space-y-4" data-testid="operations-items-table">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Item History</h2>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="rounded-lg border border-zinc-300 px-3 py-1 text-sm dark:border-zinc-600"
          data-testid="operations-items-refresh"
        >
          Refresh
        </button>
      </div>

      <div className="flex flex-wrap gap-3">
        <FilterInput
          testId="operations-items-filter-run"
          label="Run ID"
          value={filters.run_id}
          onChange={(v) => {
            setOffset(0);
            setFilters((f) => ({ ...f, run_id: v }));
          }}
        />
        <FilterSelect
          testId="operations-items-filter-action"
          label="Action"
          value={filters.action}
          options={ITEM_ACTION_OPTIONS}
          onChange={(v) => {
            setOffset(0);
            setFilters((f) => ({ ...f, action: v }));
          }}
        />
        <FilterSelect
          testId="operations-items-filter-status"
          label="Status"
          value={filters.status}
          options={ITEM_STATUS_OPTIONS}
          onChange={(v) => {
            setOffset(0);
            setFilters((f) => ({ ...f, status: v }));
          }}
        />
        <FilterInput
          testId="operations-items-filter-user"
          label="User ID"
          value={filters.user_id}
          onChange={(v) => {
            setOffset(0);
            setFilters((f) => ({ ...f, user_id: v }));
          }}
        />
        <FilterInput
          testId="operations-items-filter-employee"
          label="Employee ID"
          value={filters.employee_id}
          onChange={(v) => {
            setOffset(0);
            setFilters((f) => ({ ...f, employee_id: v }));
          }}
        />
      </div>

      <ErrorBanner message={error} />

      {loading ? (
        <p className="text-sm text-zinc-500" data-testid="operations-items-loading">
          Загрузка…
        </p>
      ) : items.length === 0 ? (
        <p className="text-sm text-zinc-500" data-testid="operations-items-empty">
          Нет items по выбранным фильтрам.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm" data-testid="operations-items-grid">
            <thead>
              <tr className="border-b border-zinc-200 text-left dark:border-zinc-700">
                {["item id", "action", "status", "user", "employee", "created", ""].map((h) => (
                  <th key={h || "actions"} className="px-2 py-2 font-medium text-zinc-600 dark:text-zinc-400">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr
                  key={row.item_id}
                  className="border-b border-zinc-100 dark:border-zinc-800"
                  data-testid={`operations-item-row-${row.item_id}`}
                >
                  <td className="px-2 py-2">#{row.item_id}</td>
                  <td className="px-2 py-2">{row.action}</td>
                  <td className="px-2 py-2">
                    <span className={`rounded px-1.5 py-0.5 text-xs ${itemStatusClass(row.status)}`}>
                      {row.status}
                    </span>
                  </td>
                  <td className="px-2 py-2">{row.login ? `${row.login} (#${row.user_id})` : `#${row.user_id}`}</td>
                  <td className="px-2 py-2">
                    {row.proposed_employee_id
                      ? `${row.employee_name ?? "—"} (#${row.proposed_employee_id})`
                      : "—"}
                  </td>
                  <td className="px-2 py-2">{formatDateTime(row.created_at)}</td>
                  <td className="px-2 py-2">
                    {onOpenItem ? (
                      <button
                        type="button"
                        className="text-blue-600 hover:underline dark:text-blue-400"
                        onClick={() => onOpenItem(row.item_id)}
                      >
                        Detail
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between text-sm text-zinc-600 dark:text-zinc-400">
        <span>
          {total} записей · стр. {page} / {totalPages}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={offset <= 0 || loading}
            onClick={() => setOffset((v) => Math.max(0, v - PAGE_SIZE))}
            className="rounded border px-2 py-1 disabled:opacity-50 dark:border-zinc-600"
          >
            ←
          </button>
          <button
            type="button"
            disabled={offset + PAGE_SIZE >= total || loading}
            onClick={() => setOffset((v) => v + PAGE_SIZE)}
            className="rounded border px-2 py-1 disabled:opacity-50 dark:border-zinc-600"
          >
            →
          </button>
        </div>
      </div>
    </section>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
  testId,
}: {
  label: string;
  value: string;
  options: readonly string[];
  onChange: (v: string) => void;
  testId: string;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="text-zinc-600 dark:text-zinc-400">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-900"
        data-testid={testId}
      >
        {options.map((opt) => (
          <option key={opt || "all"} value={opt}>
            {opt || "All"}
          </option>
        ))}
      </select>
    </label>
  );
}

function FilterInput({
  label,
  value,
  onChange,
  testId,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  testId: string;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="text-zinc-600 dark:text-zinc-400">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-900"
        data-testid={testId}
      />
    </label>
  );
}
