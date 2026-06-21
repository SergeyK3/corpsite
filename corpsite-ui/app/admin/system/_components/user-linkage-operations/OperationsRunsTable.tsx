// FILE: corpsite-ui/app/admin/system/_components/user-linkage-operations/OperationsRunsTable.tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchOperationsRuns,
  mapUserLinkageOperationsApiError,
  type UserLinkageOperationsRunListItem,
} from "../../_lib/userLinkageOperationsApi.client";
import {
  formatAuditSummary,
  OPERATION_OPTIONS,
  operationLabel,
  RUN_STATUS_OPTIONS,
  runStatusClass,
} from "../../_lib/userLinkageOperationsLabels";
import { formatActorLabel, formatDateTime } from "../../_lib/adminSystemLabels";
import ErrorBanner from "../shared/ErrorBanner";

const PAGE_SIZE = 50;

type OperationsRunsTableProps = {
  refreshToken?: number;
  initialRunId?: number | null;
  onOpenRun?: (runId: number) => void;
};

export default function OperationsRunsTable({
  refreshToken = 0,
  initialRunId = null,
  onOpenRun,
}: OperationsRunsTableProps) {
  const [items, setItems] = useState<UserLinkageOperationsRunListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    operation: "",
    status: "",
    actor_user_id: "",
    created_from: "",
    created_to: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const actorId = filters.actor_user_id ? Number(filters.actor_user_id) : undefined;
      const res = await fetchOperationsRuns({
        operation: filters.operation || undefined,
        status: filters.status || undefined,
        actor_user_id: actorId && !Number.isNaN(actorId) ? actorId : undefined,
        created_from: filters.created_from || undefined,
        created_to: filters.created_to || undefined,
        limit: PAGE_SIZE,
        offset,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(mapUserLinkageOperationsApiError(err, "Не удалось загрузить runs"));
    } finally {
      setLoading(false);
    }
  }, [filters.actor_user_id, filters.created_from, filters.created_to, filters.operation, filters.status, offset]);

  useEffect(() => {
    void load();
  }, [load, refreshToken]);

  useEffect(() => {
    if (initialRunId && onOpenRun) {
      onOpenRun(initialRunId);
    }
  }, [initialRunId, onOpenRun]);

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="space-y-4" data-testid="operations-runs-table">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">History Runs</h2>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="rounded-lg border border-zinc-300 px-3 py-1 text-sm dark:border-zinc-600"
          data-testid="operations-runs-refresh"
        >
          Refresh
        </button>
      </div>

      <div className="flex flex-wrap gap-3">
        <FilterSelect
          testId="operations-runs-filter-operation"
          label="Operation"
          value={filters.operation}
          options={OPERATION_OPTIONS}
          onChange={(v) => {
            setOffset(0);
            setFilters((f) => ({ ...f, operation: v }));
          }}
        />
        <FilterSelect
          testId="operations-runs-filter-status"
          label="Status"
          value={filters.status}
          options={RUN_STATUS_OPTIONS}
          onChange={(v) => {
            setOffset(0);
            setFilters((f) => ({ ...f, status: v }));
          }}
        />
        <FilterInput
          testId="operations-runs-filter-actor"
          label="Actor user ID"
          value={filters.actor_user_id}
          onChange={(v) => {
            setOffset(0);
            setFilters((f) => ({ ...f, actor_user_id: v }));
          }}
        />
        <FilterInput
          testId="operations-runs-filter-from"
          label="From"
          type="datetime-local"
          value={filters.created_from}
          onChange={(v) => {
            setOffset(0);
            setFilters((f) => ({ ...f, created_from: v }));
          }}
        />
        <FilterInput
          testId="operations-runs-filter-to"
          label="To"
          type="datetime-local"
          value={filters.created_to}
          onChange={(v) => {
            setOffset(0);
            setFilters((f) => ({ ...f, created_to: v }));
          }}
        />
      </div>

      <ErrorBanner message={error} />

      {loading ? (
        <p className="text-sm text-zinc-500" data-testid="operations-runs-loading">
          Загрузка…
        </p>
      ) : items.length === 0 ? (
        <p className="text-sm text-zinc-500" data-testid="operations-runs-empty">
          Нет runs по выбранным фильтрам.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm" data-testid="operations-runs-grid">
            <thead>
              <tr className="border-b border-zinc-200 text-left dark:border-zinc-700">
                {["run id", "operation", "actor", "created", "status", "items", "audit count", ""].map((h) => (
                  <th key={h || "actions"} className="px-2 py-2 font-medium text-zinc-600 dark:text-zinc-400">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr
                  key={row.run_id}
                  className="border-b border-zinc-100 dark:border-zinc-800"
                  data-testid={`operations-run-row-${row.run_id}`}
                >
                  <td className="px-2 py-2">#{row.run_id}</td>
                  <td className="px-2 py-2">{operationLabel(row.operation)}</td>
                  <td className="px-2 py-2">{row.actor_login ?? formatActorLabel(row.actor_user_id)}</td>
                  <td className="px-2 py-2">{formatDateTime(row.started_at)}</td>
                  <td className="px-2 py-2">
                    <span className={`rounded px-1.5 py-0.5 text-xs ${runStatusClass(row.status)}`}>
                      {row.status}
                    </span>
                  </td>
                  <td className="px-2 py-2">{row.item_count}</td>
                  <td className="px-2 py-2">{formatAuditSummary(row.audit_summary)}</td>
                  <td className="px-2 py-2">
                    {onOpenRun ? (
                      <button
                        type="button"
                        className="text-blue-600 hover:underline dark:text-blue-400"
                        onClick={() => onOpenRun(row.run_id)}
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

      <Pagination
        page={page}
        totalPages={totalPages}
        total={total}
        loading={loading}
        offset={offset}
        pageSize={PAGE_SIZE}
        onPrev={() => setOffset((v) => Math.max(0, v - PAGE_SIZE))}
        onNext={() => setOffset((v) => v + PAGE_SIZE)}
      />
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
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  testId: string;
  type?: string;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="text-zinc-600 dark:text-zinc-400">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded border px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-900"
        data-testid={testId}
      />
    </label>
  );
}

function Pagination({
  page,
  totalPages,
  total,
  loading,
  offset,
  pageSize,
  onPrev,
  onNext,
}: {
  page: number;
  totalPages: number;
  total: number;
  loading: boolean;
  offset: number;
  pageSize: number;
  onPrev: () => void;
  onNext: () => void;
}) {
  return (
    <div className="flex items-center justify-between text-sm text-zinc-600 dark:text-zinc-400">
      <span>
        {total} записей · стр. {page} / {totalPages}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={offset <= 0 || loading}
          onClick={onPrev}
          className="rounded border px-2 py-1 disabled:opacity-50 dark:border-zinc-600"
        >
          ←
        </button>
        <button
          type="button"
          disabled={offset + pageSize >= total || loading}
          onClick={onNext}
          className="rounded border px-2 py-1 disabled:opacity-50 dark:border-zinc-600"
        >
          →
        </button>
      </div>
    </div>
  );
}
