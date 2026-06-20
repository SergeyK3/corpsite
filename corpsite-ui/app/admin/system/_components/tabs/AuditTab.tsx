// FILE: corpsite-ui/app/admin/system/_components/tabs/AuditTab.tsx
"use client";

import { Fragment, useCallback, useEffect, useState } from "react";

import {
  fetchSecurityAudit,
  mapAdminSystemApiError,
  type SecurityAuditEvent,
} from "../../_lib/adminSystemApi.client";
import {
  auditEventClass,
  formatDateTime,
  metadataHasSensitiveKeys,
} from "../../_lib/adminSystemLabels";
import ErrorBanner from "../shared/ErrorBanner";

export default function AuditTab() {
  const [items, setItems] = useState<SecurityAuditEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);

  const [filters, setFilters] = useState({
    event_type: "",
    actor_user_id: "",
    target_user_id: "",
    target_person_id: "",
    target_employee_id: "",
    date_from: "",
    date_to: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSecurityAudit({
        event_type: filters.event_type || undefined,
        actor_user_id: filters.actor_user_id ? Number(filters.actor_user_id) : undefined,
        target_user_id: filters.target_user_id ? Number(filters.target_user_id) : undefined,
        target_person_id: filters.target_person_id ? Number(filters.target_person_id) : undefined,
        target_employee_id: filters.target_employee_id ? Number(filters.target_employee_id) : undefined,
        date_from: filters.date_from || undefined,
        date_to: filters.date_to || undefined,
        limit: 100,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(mapAdminSystemApiError(err, "Не удалось загрузить audit log"));
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="space-y-4">
      <ErrorBanner message={error} />

      <div className="grid gap-2 rounded-lg border border-zinc-200 p-4 sm:grid-cols-2 lg:grid-cols-3 dark:border-zinc-700">
        <label className="text-xs">
          event_type
          <input
            value={filters.event_type}
            onChange={(e) => setFilters({ ...filters, event_type: e.target.value })}
            className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
          />
        </label>
        <label className="text-xs">
          actor_user_id
          <input
            value={filters.actor_user_id}
            onChange={(e) => setFilters({ ...filters, actor_user_id: e.target.value })}
            className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
          />
        </label>
        <label className="text-xs">
          target_user_id
          <input
            value={filters.target_user_id}
            onChange={(e) => setFilters({ ...filters, target_user_id: e.target.value })}
            className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
          />
        </label>
        <label className="text-xs">
          target_person_id
          <input
            value={filters.target_person_id}
            onChange={(e) => setFilters({ ...filters, target_person_id: e.target.value })}
            className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
          />
        </label>
        <label className="text-xs">
          target_employee_id
          <input
            value={filters.target_employee_id}
            onChange={(e) => setFilters({ ...filters, target_employee_id: e.target.value })}
            className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
          />
        </label>
        <label className="text-xs">
          date_from
          <input
            type="datetime-local"
            value={filters.date_from}
            onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
            className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
          />
        </label>
        <label className="text-xs">
          date_to
          <input
            type="datetime-local"
            value={filters.date_to}
            onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
            className="mt-1 w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
          />
        </label>
        <button
          type="button"
          onClick={() => void load()}
          className="self-end rounded-lg bg-blue-600 px-3 py-2 text-sm text-white"
        >
          Применить фильтры
        </button>
      </div>

      <p className="text-sm text-zinc-600">Событий: {total} (newest first)</p>

      {loading ? (
        <p className="text-sm text-zinc-500">Загрузка…</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
          <table className="min-w-full text-sm">
            <thead className="bg-zinc-50 dark:bg-zinc-900">
              <tr>
                <th className="px-3 py-2 text-left">ID</th>
                <th className="px-3 py-2 text-left">When</th>
                <th className="px-3 py-2 text-left">Event</th>
                <th className="px-3 py-2 text-left">Actor</th>
                <th className="px-3 py-2 text-left">Targets</th>
                <th className="px-3 py-2 text-left"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((ev) => {
                const sensitive = metadataHasSensitiveKeys(ev.metadata);
                return (
                  <Fragment key={ev.audit_id}>
                    <tr className="border-t dark:border-zinc-800">
                      <td className="px-3 py-2">{ev.audit_id}</td>
                      <td className="px-3 py-2">{formatDateTime(ev.happened_at)}</td>
                      <td className="px-3 py-2">
                        <span
                          className={`rounded px-2 py-0.5 text-xs font-medium ${auditEventClass(ev.event_type)}`}
                        >
                          {ev.event_type}
                        </span>
                      </td>
                      <td className="px-3 py-2">{ev.actor_user_id ?? "—"}</td>
                      <td className="px-3 py-2 text-xs">
                        u:{ev.target_user_id ?? "—"} p:{ev.target_person_id ?? "—"} e:
                        {ev.target_employee_id ?? "—"}
                      </td>
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          className="text-xs underline"
                          onClick={() =>
                            setExpanded(expanded === ev.audit_id ? null : ev.audit_id)
                          }
                        >
                          metadata
                        </button>
                      </td>
                    </tr>
                    {expanded === ev.audit_id ? (
                      <tr className="bg-zinc-50 dark:bg-zinc-900">
                        <td colSpan={6} className="px-3 py-2">
                          {sensitive.length ? (
                            <p className="mb-2 text-xs font-medium text-red-600">
                              Warning: sensitive keys in metadata: {sensitive.join(", ")}
                            </p>
                          ) : null}
                          <pre className="max-h-40 overflow-auto text-xs">
                            {JSON.stringify(ev.metadata ?? {}, null, 2)}
                          </pre>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
