// FILE: corpsite-ui/app/directory/personnel/_components/PersonnelJournalPageClient.tsx
"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import EmployeeDrawer from "../../employees/_components/EmployeeDrawer";
import PersonnelSubNav from "./PersonnelSubNav";
import {
  listPersonnelEvents,
  mapDemoApiError,
  type PersonnelEventRow,
} from "../_lib/demoApi.client";

const EVENT_TYPES = [
  { value: "", label: "Все" },
  { value: "HIRE", label: "Приём" },
  { value: "TRANSFER", label: "Перевод" },
  { value: "CORRECTION", label: "Исправление" },
  { value: "TERMINATION", label: "Увольнение" },
] as const;

const EVENT_BADGE: Record<string, string> = {
  HIRE: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-200",
  TRANSFER: "bg-blue-100 text-blue-900 dark:bg-blue-950/50 dark:text-blue-200",
  CORRECTION: "bg-amber-100 text-amber-900 dark:bg-amber-950/50 dark:text-amber-200",
  TERMINATION: "bg-zinc-200 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200",
};

const EVENT_LABEL: Record<string, string> = {
  HIRE: "Приём",
  TRANSFER: "Перевод",
  CORRECTION: "Исправление",
  TERMINATION: "Увольнение",
};

function fmtDate(v: string | null | undefined): string {
  if (!v) return "—";
  const dt = new Date(v);
  if (Number.isNaN(dt.getTime())) return v;
  return dt.toLocaleDateString("ru-RU");
}

function fmtOrderRef(v: string | null | undefined): React.ReactNode {
  const value = String(v ?? "").trim();
  if (!value) return "—";
  return (
    <span className="inline-flex max-w-[12rem] truncate rounded border border-zinc-200 bg-zinc-50 px-1.5 py-0.5 font-mono text-xs font-semibold tracking-tight text-zinc-800 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100">
      {value}
    </span>
  );
}

function orgUnitsUnchanged(row: PersonnelEventRow): boolean {
  if (row.from_org_unit_id != null && row.to_org_unit_id != null) {
    return row.from_org_unit_id === row.to_org_unit_id;
  }
  const from = String(row.from_org_unit_name ?? "").trim();
  const to = String(row.to_org_unit_name ?? "").trim();
  return Boolean(from && to && from === to);
}

function renderOrgUnitCells(row: PersonnelEventRow): React.ReactNode {
  const typeKey = String(row.event_type || "").toUpperCase();

  if (typeKey === "HIRE") {
    return (
      <>
        <td className="px-3 py-2 text-zinc-500 dark:text-zinc-400">—</td>
        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
          {row.to_org_unit_name || "—"}
        </td>
      </>
    );
  }

  if (typeKey === "TERMINATION") {
    return (
      <>
        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
          {row.from_org_unit_name || "—"}
        </td>
        <td className="px-3 py-2 text-zinc-500 dark:text-zinc-400">—</td>
      </>
    );
  }

  if (typeKey === "CORRECTION" && orgUnitsUnchanged(row)) {
    const unit = row.to_org_unit_name || row.from_org_unit_name;
    return (
      <td colSpan={2} className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
        {unit ? (
          <>
            <span>{unit}</span>
            <span className="text-zinc-500 dark:text-zinc-400"> · Корректировка данных</span>
          </>
        ) : (
          <span className="text-zinc-500 dark:text-zinc-400">Корректировка данных</span>
        )}
      </td>
    );
  }

  return (
    <>
      <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
        {row.from_org_unit_name || "—"}
      </td>
      <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
        {row.to_org_unit_name || "—"}
      </td>
    </>
  );
}

export default function PersonnelJournalPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [items, setItems] = React.useState<PersonnelEventRow[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerEmployeeId, setDrawerEmployeeId] = React.useState<string | null>(null);

  const eventType = searchParams.get("event_type") || "";
  const dateFrom = searchParams.get("date_from") || "";
  const dateTo = searchParams.get("date_to") || "";

  const load = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await listPersonnelEvents({
        event_type: eventType || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit: 200,
        offset: 0,
      });
      setItems(Array.isArray(body.items) ? body.items : []);
      setTotal(Number(body.total) || 0);
    } catch (e) {
      setItems([]);
      setTotal(0);
      setError(mapDemoApiError(e, "Не удалось загрузить кадровый журнал"));
    } finally {
      setLoading(false);
    }
  }, [eventType, dateFrom, dateTo]);

  React.useEffect(() => {
    void load();
  }, [load]);

  function updateFilters(next: { event_type?: string; date_from?: string; date_to?: string }) {
    const params = new URLSearchParams(searchParams.toString());
    if (next.event_type !== undefined) {
      if (next.event_type) params.set("event_type", next.event_type);
      else params.delete("event_type");
    }
    if (next.date_from !== undefined) {
      if (next.date_from) params.set("date_from", next.date_from);
      else params.delete("date_from");
    }
    if (next.date_to !== undefined) {
      if (next.date_to) params.set("date_to", next.date_to);
      else params.delete("date_to");
    }
    const qs = params.toString();
    router.replace(qs ? `?${qs}` : "/directory/personnel/journal");
  }

  function openEmployee(id: number) {
    setDrawerEmployeeId(String(id));
    setDrawerOpen(true);
  }

  return (
    <div className="space-y-4">
      <PersonnelSubNav />

      <div>
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Кадровый журнал</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          История кадровых событий организации
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Тип события
          </label>
          <select
            value={eventType}
            onChange={(e) => updateFilters({ event_type: e.target.value })}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            {EVENT_TYPES.map((t) => (
              <option key={t.value || "all"} value={t.value}>
                {t.label}
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
            value={dateFrom}
            onChange={(e) => updateFilters({ date_from: e.target.value })}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Дата по
          </label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => updateFilters({ date_to: e.target.value })}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          />
        </div>
        <div className="text-sm text-zinc-500 dark:text-zinc-400">
          {loading ? "Загрузка…" : `${total} событий`}
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
          {error}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr className="bg-zinc-100 text-left dark:bg-zinc-900">
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Дата
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Сотрудник
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Тип
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Из отделения
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  В отделение
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Приказ
                </th>
              </tr>
            </thead>
            <tbody>
              {!loading && items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-zinc-500">
                    Кадровые события не найдены
                  </td>
                </tr>
              ) : null}
              {items.map((row) => {
                const typeKey = String(row.event_type || "").toUpperCase();
                return (
                  <tr
                    key={row.event_id}
                    onClick={() => openEmployee(row.employee_id)}
                    className="cursor-pointer border-t border-zinc-200 hover:bg-blue-50/60 dark:border-zinc-800 dark:hover:bg-blue-950/20"
                  >
                    <td className="px-3 py-2 whitespace-nowrap">{fmtDate(row.effective_date)}</td>
                    <td className="px-3 py-2 font-medium text-zinc-900 dark:text-zinc-50">
                      {row.employee_name || `#${row.employee_id}`}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${
                          EVENT_BADGE[typeKey] ||
                          "bg-zinc-100 text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200"
                        }`}
                      >
                        {EVENT_LABEL[typeKey] || typeKey}
                      </span>
                    </td>
                    {renderOrgUnitCells(row)}
                    <td className="px-3 py-2">{fmtOrderRef(row.order_ref)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <EmployeeDrawer
        employeeId={drawerEmployeeId}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
