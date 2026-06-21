// FILE: corpsite-ui/app/admin/system/_components/personnel-lifecycle/OverridesPanel.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchOverride,
  fetchOverrides,
  mapPersonnelLifecycleApiError,
  type OverrideDetail,
  type OverrideSummary,
} from "../../_lib/personnelLifecycleApi.client";
import { formatDateTime } from "../../_lib/adminSystemLabels";
import { overrideStatusClass } from "../../_lib/personnelLifecycleLabels";
import ErrorBanner from "../shared/ErrorBanner";
import OverrideDetailDrawer from "./OverrideDetailDrawer";

const PAGE_SIZE = 100;

type OverridesPanelProps = {
  hasHrGovernance: boolean;
};

export default function OverridesPanel({ hasHrGovernance }: OverridesPanelProps) {
  const [items, setItems] = useState<OverrideSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    status: "",
    tier: "",
    owner_domain: "",
    field_path: "",
  });
  const [selected, setSelected] = useState<OverrideDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchOverrides({
        status: filters.status || undefined,
        field_path: filters.field_path || undefined,
        limit: PAGE_SIZE,
        offset,
        sort_by: "created_at",
        sort_dir: "desc",
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(mapPersonnelLifecycleApiError(err, "Не удалось загрузить overrides"));
    } finally {
      setLoading(false);
    }
  }, [filters.status, filters.field_path, offset, reloadToken]);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredItems = useMemo(() => {
    return items.filter((row) => {
      if (filters.tier && String(row.tier) !== filters.tier.trim()) return false;
      if (
        filters.owner_domain &&
        !row.owner_domain.toLowerCase().includes(filters.owner_domain.trim().toLowerCase())
      ) {
        return false;
      }
      return true;
    });
  }, [items, filters.tier, filters.owner_domain]);

  async function openOverride(overrideId: number): Promise<void> {
    setDrawerOpen(true);
    setDetailLoading(true);
    setSelected(null);
    try {
      const detail = await fetchOverride(overrideId);
      setSelected(detail);
    } catch (err) {
      setError(mapPersonnelLifecycleApiError(err, "Не удалось загрузить override"));
      setDrawerOpen(false);
    } finally {
      setDetailLoading(false);
    }
  }

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="space-y-4" data-testid="overrides-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Исключения</h2>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="rounded-lg border border-zinc-300 px-3 py-1 text-sm dark:border-zinc-600"
        >
          Обновить
        </button>
      </div>

      <ErrorBanner message={error} />

      <div className="grid gap-2 rounded-lg border border-zinc-200 p-4 sm:grid-cols-2 lg:grid-cols-4 dark:border-zinc-700">
        {(
          [
            ["status", "status"],
            ["tier", "tier"],
            ["owner_domain", "owner_domain"],
            ["field_path", "field_path"],
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="text-xs">
            {label}
            <input
              value={filters[key]}
              onChange={(e) => {
                setOffset(0);
                setFilters((prev) => ({ ...prev, [key]: e.target.value }));
              }}
              className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
              data-testid={`overrides-filter-${key}`}
            />
          </label>
        ))}
      </div>

      {filters.tier || filters.owner_domain ? (
        <p className="text-xs text-zinc-500">
          Фильтры tier и owner_domain применяются к текущей странице (API C4.1 поддерживает status и field_path).
        </p>
      ) : null}

      {loading ? (
        <p className="text-sm text-zinc-500" data-testid="overrides-loading">
          Загрузка…
        </p>
      ) : filteredItems.length === 0 ? (
        <p className="text-sm text-zinc-500" data-testid="overrides-empty">
          Нет исключений.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm" data-testid="overrides-table">
            <thead>
              <tr className="border-b border-zinc-200 text-left dark:border-zinc-700">
                {[
                  "override_id",
                  "scope_type",
                  "field_path",
                  "tier",
                  "status",
                  "owner_domain",
                  "created_by",
                  "created_at",
                ].map((h) => (
                  <th key={h} className="px-2 py-2 font-medium text-zinc-600 dark:text-zinc-400">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((row) => (
                <tr
                  key={row.override_id}
                  className="cursor-pointer border-b border-zinc-100 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
                  onClick={() => void openOverride(row.override_id)}
                  data-testid={`override-row-${row.override_id}`}
                >
                  <td className="px-2 py-2">{row.override_id}</td>
                  <td className="px-2 py-2">{row.scope_type}</td>
                  <td className="px-2 py-2">{row.field_path}</td>
                  <td className="px-2 py-2">{row.tier}</td>
                  <td className="px-2 py-2">
                    <span className={`rounded px-1.5 py-0.5 text-xs ${overrideStatusClass(row.status)}`}>
                      {row.status}
                    </span>
                  </td>
                  <td className="px-2 py-2">{row.owner_domain}</td>
                  <td className="px-2 py-2">—</td>
                  <td className="px-2 py-2">{formatDateTime(row.created_at)}</td>
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

      <OverrideDetailDrawer
        detail={selected}
        loading={detailLoading}
        open={drawerOpen}
        hasHrGovernance={hasHrGovernance}
        onClose={() => {
          setDrawerOpen(false);
          setSelected(null);
        }}
        onUpdated={() => {
          setReloadToken((v) => v + 1);
          if (selected) void openOverride(selected.override_id);
        }}
      />
    </section>
  );
}
