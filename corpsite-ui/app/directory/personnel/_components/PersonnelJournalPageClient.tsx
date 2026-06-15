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
  { value: "POSITION_CHANGE", label: "Смена должности" },
  { value: "RATE_CHANGE", label: "Изменение ставки" },
  { value: "CORRECTION", label: "Исправление" },
  { value: "TERMINATION", label: "Увольнение" },
] as const;

const EVENT_BADGE: Record<string, string> = {
  HIRE: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-200",
  TRANSFER: "bg-blue-100 text-blue-900 dark:bg-blue-950/50 dark:text-blue-200",
  POSITION_CHANGE: "bg-violet-100 text-violet-900 dark:bg-violet-950/50 dark:text-violet-200",
  RATE_CHANGE: "bg-cyan-100 text-cyan-900 dark:bg-cyan-950/50 dark:text-cyan-200",
  CORRECTION: "bg-amber-100 text-amber-900 dark:bg-amber-950/50 dark:text-amber-200",
  TERMINATION: "bg-zinc-200 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200",
};

const EVENT_LABEL: Record<string, string> = {
  HIRE: "Приём",
  TRANSFER: "Перевод",
  POSITION_CHANGE: "Смена должности",
  RATE_CHANGE: "Изменение ставки",
  CORRECTION: "Исправление",
  TERMINATION: "Увольнение",
};

function eventRowLabel(row: PersonnelEventRow): string {
  const fromApi = String(row.event_label ?? "").trim();
  if (fromApi) return fromApi;
  const typeKey = String(row.event_type || "").toUpperCase();
  return EVENT_LABEL[typeKey] || typeKey || "—";
}

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

function fmtRate(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(Number(v))) return "—";
  return String(parseFloat(Number(v).toFixed(2)));
}

function nameOrDash(v: string | null | undefined): string {
  const s = String(v ?? "").trim();
  return s || "—";
}

function formatEventDetails(row: PersonnelEventRow): string[] {
  const typeKey = String(row.event_type || "").toUpperCase();

  if (typeKey === "HIRE") {
    return [
      `Отделение: ${nameOrDash(row.to_org_unit_name)}`,
      `Должность: ${nameOrDash(row.to_position_name)}`,
      `Ставка: ${fmtRate(row.to_rate)}`,
    ];
  }

  if (typeKey === "TERMINATION") {
    return [
      `Отделение: ${nameOrDash(row.from_org_unit_name)}`,
      `Должность: ${nameOrDash(row.from_position_name)}`,
      `Ставка: ${fmtRate(row.from_rate)}`,
    ];
  }

  if (typeKey === "POSITION_CHANGE") {
    const lines: string[] = [
      `Отделение: ${nameOrDash(row.to_org_unit_name || row.from_org_unit_name)}`,
    ];
    const fromPos = nameOrDash(row.from_position_name);
    const toPos = nameOrDash(row.to_position_name);
    if (fromPos !== toPos) {
      lines.push(`Должность: ${fromPos} → ${toPos}`);
    } else if (toPos !== "—") {
      lines.push(`Должность: ${toPos}`);
    }
    const fromRate = fmtRate(row.from_rate);
    const toRate = fmtRate(row.to_rate);
    if (fromRate !== toRate && toRate !== "—") {
      lines.push(`Ставка: ${fromRate} → ${toRate}`);
    }
    return lines;
  }

  if (typeKey === "RATE_CHANGE") {
    return [
      `Отделение: ${nameOrDash(row.to_org_unit_name || row.from_org_unit_name)}`,
      `Должность: ${nameOrDash(row.to_position_name || row.from_position_name)}`,
      `Ставка: ${fmtRate(row.from_rate)} → ${fmtRate(row.to_rate)}`,
    ];
  }

  if (typeKey === "CORRECTION" && orgUnitsUnchanged(row)) {
    const lines: string[] = [];
    const unit = nameOrDash(row.to_org_unit_name || row.from_org_unit_name);
    lines.push(`Отделение: ${unit}`);

    const fromPos = nameOrDash(row.from_position_name);
    const toPos = nameOrDash(row.to_position_name);
    if (fromPos !== toPos) {
      lines.push(`Должность: ${fromPos} → ${toPos}`);
    } else if (toPos !== "—") {
      lines.push(`Должность: ${toPos}`);
    }

    const fromRate = fmtRate(row.from_rate);
    const toRate = fmtRate(row.to_rate);
    if (fromRate !== toRate) {
      lines.push(`Ставка: ${fromRate} → ${toRate}`);
    } else if (toRate !== "—") {
      lines.push(`Ставка: ${toRate}`);
    }

    if (lines.length === 1) {
      lines.push("Корректировка данных");
    }
    return lines;
  }

  return [
    `Отделение: ${nameOrDash(row.from_org_unit_name)} → ${nameOrDash(row.to_org_unit_name)}`,
    `Должность: ${nameOrDash(row.from_position_name)} → ${nameOrDash(row.to_position_name)}`,
    `Ставка: ${fmtRate(row.from_rate)} → ${fmtRate(row.to_rate)}`,
  ];
}

function renderEventDetails(row: PersonnelEventRow): React.ReactNode {
  const lines = formatEventDetails(row);
  return (
    <div className="min-w-[14rem] max-w-[22rem] space-y-0.5 text-xs leading-snug text-zinc-600 dark:text-zinc-400">
      {lines.map((line) => (
        <div key={line}>{line}</div>
      ))}
    </div>
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

  if (
    (typeKey === "POSITION_CHANGE" || typeKey === "RATE_CHANGE") &&
    orgUnitsUnchanged(row)
  ) {
    const unit = row.to_org_unit_name || row.from_org_unit_name;
    return (
      <td colSpan={2} className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
        {unit || "—"}
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
  const employeeSearch = searchParams.get("q") || "";

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

  const filteredItems = React.useMemo(() => {
    const q = employeeSearch.trim().toLowerCase();
    if (!q) return items;
    return items.filter((row) => {
      const name = String(row.employee_name || "").toLowerCase();
      return name.includes(q) || String(row.employee_id).includes(q);
    });
  }, [employeeSearch, items]);

  function updateFilters(next: {
    event_type?: string;
    date_from?: string;
    date_to?: string;
    q?: string;
  }) {
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
    if (next.q !== undefined) {
      if (next.q.trim()) params.set("q", next.q.trim());
      else params.delete("q");
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
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Поиск сотрудника
          </label>
          <input
            type="search"
            value={employeeSearch}
            onChange={(e) => updateFilters({ q: e.target.value })}
            placeholder="ФИО или таб. №"
            className="min-w-[12rem] rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          />
        </div>
        <div className="text-sm text-zinc-500 dark:text-zinc-400">
          {loading
            ? "Загрузка…"
            : employeeSearch.trim()
              ? `${filteredItems.length} из ${total} событий`
              : `${total} событий`}
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
                  Событие
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Из отделения
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  В отделение
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Детали
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Приказ
                </th>
              </tr>
            </thead>
            <tbody>
              {!loading && filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-3 py-8 text-center text-zinc-500">
                    {items.length === 0
                      ? "Кадровые события не найдены"
                      : "События не найдены по выбранным фильтрам"}
                  </td>
                </tr>
              ) : null}
              {filteredItems.map((row) => {
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
                        {eventRowLabel(row)}
                      </span>
                    </td>
                    {renderOrgUnitCells(row)}
                    <td className="px-3 py-2 align-top">{renderEventDetails(row)}</td>
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
