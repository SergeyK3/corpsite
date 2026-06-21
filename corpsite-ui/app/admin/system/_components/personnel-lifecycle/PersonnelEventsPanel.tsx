// FILE: corpsite-ui/app/admin/system/_components/personnel-lifecycle/PersonnelEventsPanel.tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  fetchPersonnelEvent,
  fetchPersonnelEvents,
  mapPersonnelLifecycleApiError,
  type PersonnelEventDetail,
  type PersonnelEventSummary,
} from "../../_lib/personnelLifecycleApi.client";
import { formatDateTime } from "../../_lib/adminSystemLabels";
import ErrorBanner from "../shared/ErrorBanner";
import PersonnelEventDrawer from "./PersonnelEventDrawer";

const PAGE_SIZE = 100;

export default function PersonnelEventsPanel() {
  const [items, setItems] = useState<PersonnelEventSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    snapshot_id: "",
    event_type: "",
    status: "",
    person_key: "",
    assignment_key: "",
    date_from: "",
    date_to: "",
  });
  const [selected, setSelected] = useState<PersonnelEventDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchPersonnelEvents({
        snapshot_id: filters.snapshot_id ? Number(filters.snapshot_id) : undefined,
        event_type: filters.event_type || undefined,
        status: filters.status || undefined,
        person_key: filters.person_key || undefined,
        assignment_key: filters.assignment_key || undefined,
        date_from: filters.date_from || undefined,
        date_to: filters.date_to || undefined,
        limit: PAGE_SIZE,
        offset,
        sort_by: "detected_at",
        sort_dir: "desc",
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(mapPersonnelLifecycleApiError(err, "Не удалось загрузить personnel events"));
    } finally {
      setLoading(false);
    }
  }, [filters, offset]);

  useEffect(() => {
    void load();
  }, [load]);

  async function openEvent(eventId: number): Promise<void> {
    setDrawerOpen(true);
    setDetailLoading(true);
    setSelected(null);
    try {
      const detail = await fetchPersonnelEvent(eventId);
      setSelected(detail);
    } catch (err) {
      setError(mapPersonnelLifecycleApiError(err, "Не удалось загрузить событие"));
      setDrawerOpen(false);
    } finally {
      setDetailLoading(false);
    }
  }

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className="space-y-4" data-testid="personnel-events-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">События персонала</h2>
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

      <div className="grid gap-2 rounded-lg border border-zinc-200 p-4 sm:grid-cols-2 lg:grid-cols-3 dark:border-zinc-700">
        {(
          [
            ["snapshot_id", "snapshot"],
            ["event_type", "event_type"],
            ["status", "status"],
            ["person_key", "person_key"],
            ["assignment_key", "assignment_key"],
            ["date_from", "date_from"],
            ["date_to", "date_to"],
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
              data-testid={`personnel-events-filter-${key}`}
            />
          </label>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-zinc-500" data-testid="personnel-events-loading">
          Загрузка…
        </p>
      ) : items.length === 0 ? (
        <p className="text-sm text-zinc-500" data-testid="personnel-events-empty">
          Нет событий персонала.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm" data-testid="personnel-events-table">
            <thead>
              <tr className="border-b border-zinc-200 text-left dark:border-zinc-700">
                {[
                  "event_id",
                  "event_type",
                  "status",
                  "person_key",
                  "assignment_key",
                  "detected_at",
                  "resolved_at",
                ].map((h) => (
                  <th key={h} className="px-2 py-2 font-medium text-zinc-600 dark:text-zinc-400">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr
                  key={row.personnel_event_id}
                  className="cursor-pointer border-b border-zinc-100 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
                  onClick={() => void openEvent(row.personnel_event_id)}
                  data-testid={`personnel-event-row-${row.personnel_event_id}`}
                >
                  <td className="px-2 py-2">{row.personnel_event_id}</td>
                  <td className="px-2 py-2">{row.event_type}</td>
                  <td className="px-2 py-2">{row.status}</td>
                  <td className="px-2 py-2 max-w-[12rem] truncate">{row.person_key}</td>
                  <td className="px-2 py-2 max-w-[12rem] truncate">{row.assignment_key ?? "—"}</td>
                  <td className="px-2 py-2">{formatDateTime(row.detected_at)}</td>
                  <td className="px-2 py-2">{formatDateTime(row.resolved_at)}</td>
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

      <PersonnelEventDrawer
        event={selected}
        loading={detailLoading}
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          setSelected(null);
        }}
      />
    </section>
  );
}
