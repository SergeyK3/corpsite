// FILE: corpsite-ui/app/directory/personnel/_components/ProfessionalDocumentsPageClient.tsx
"use client";

import * as React from "react";

import EmployeeDrawer from "../../employees/_components/EmployeeDrawer";
import {
  countDocumentsByStatus,
  DOCUMENT_QUICK_FILTERS,
  DOCUMENT_STATUS_META,
  DOCUMENT_STATUS_SUMMARY_ORDER,
  fmtProfileDate,
  getEmployeeProfessionalContext,
  matchesDocumentQuickFilter,
  type DocumentQuickFilter,
} from "../../employees/_lib/professionalProfile";
import PersonnelSubNav from "./PersonnelSubNav";
import {
  listProfessionalDocuments,
  mapDemoApiError,
  type ProfessionalDocumentRow,
} from "../_lib/demoApi.client";

const STATUS_FILTER_OPTIONS = [
  { value: "", label: "Все статусы" },
  ...DOCUMENT_STATUS_SUMMARY_ORDER.map((status) => ({
    value: status,
    label: DOCUMENT_STATUS_META[status]?.label ?? status,
  })),
];

type EnrichedRow = ProfessionalDocumentRow & {
  mainSpecialty: string;
  category: string;
};

function statusMeta(status: string) {
  const key = String(status || "").toUpperCase();
  return (
    DOCUMENT_STATUS_META[key] ?? {
      label: status,
      className: "bg-zinc-100 text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200",
    }
  );
}

export default function ProfessionalDocumentsPageClient() {
  const [items, setItems] = React.useState<ProfessionalDocumentRow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [unavailable, setUnavailable] = React.useState(false);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerEmployeeId, setDrawerEmployeeId] = React.useState<string | null>(null);

  const [quickFilter, setQuickFilter] = React.useState<DocumentQuickFilter>("ALL");
  const [statusFilter, setStatusFilter] = React.useState("");
  const [documentFilter, setDocumentFilter] = React.useState("");
  const [employeeSearch, setEmployeeSearch] = React.useState("");

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const body = await listProfessionalDocuments();
        if (cancelled) return;
        if (body.available === false) {
          setUnavailable(true);
          setItems([]);
          return;
        }
        setUnavailable(false);
        setItems(Array.isArray(body.items) ? body.items : []);
      } catch (e) {
        if (cancelled) return;
        setItems([]);
        setError(mapDemoApiError(e, "Не удалось загрузить профессиональные документы"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const enrichedItems = React.useMemo<EnrichedRow[]>(() => {
    return items.map((row) => {
      const ctx = getEmployeeProfessionalContext(row.employee_id, items);
      return {
        ...row,
        mainSpecialty: ctx.mainSpecialty,
        category: ctx.category,
      };
    });
  }, [items]);

  const documentTypes = React.useMemo(() => {
    const names = new Set<string>();
    for (const row of items) {
      const name = String(row.certificate_type_name || "").trim();
      if (name) names.add(name);
    }
    return [...names].sort((a, b) => a.localeCompare(b, "ru"));
  }, [items]);

  const statusCounts = React.useMemo(() => countDocumentsByStatus(items), [items]);

  const filteredItems = React.useMemo(() => {
    const search = employeeSearch.trim().toLowerCase();
    return enrichedItems.filter((row) => {
      const status = String(row.status || "").toUpperCase();

      if (!matchesDocumentQuickFilter(status, quickFilter)) {
        return false;
      }
      if (statusFilter && status !== statusFilter) {
        return false;
      }
      if (documentFilter && row.certificate_type_name !== documentFilter) {
        return false;
      }
      if (search) {
        const name = String(row.employee_name || "").toLowerCase();
        if (!name.includes(search)) return false;
      }
      return true;
    });
  }, [documentFilter, employeeSearch, enrichedItems, quickFilter, statusFilter]);

  function handleQuickFilter(value: DocumentQuickFilter) {
    setQuickFilter(value);
    if (value === "ALL" || value === "PROBLEMATIC" || !value) {
      setStatusFilter("");
      return;
    }
    setStatusFilter(value);
  }

  function handleStatusDropdown(value: string) {
    setStatusFilter(value);
    if (!value) {
      setQuickFilter("ALL");
      return;
    }
    const chip = DOCUMENT_QUICK_FILTERS.find((c) => c.value === value);
    setQuickFilter(chip ? (chip.value as DocumentQuickFilter) : "");
  }

  const tableColSpan = 6;

  return (
    <div className="space-y-4">
      <PersonnelSubNav />

      <div>
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
          Реестр профессиональных документов
        </h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Сводный реестр для контроля сроков. Источник данных для профиля сотрудника.
        </p>
      </div>

      {unavailable ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/55 dark:bg-amber-950/35 dark:text-amber-200">
          Локальная демонстрация ADR-034 недоступна: таблицы не установлены. См.{" "}
          <code className="text-xs">docs/demo/HR-DEMO-LOCAL-RUNBOOK.md</code>.
        </div>
      ) : null}

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
          {error}
        </div>
      ) : null}

      {!unavailable && !loading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
          {DOCUMENT_STATUS_SUMMARY_ORDER.map((statusKey) => {
            const meta = DOCUMENT_STATUS_META[statusKey];
            const active = quickFilter === statusKey || statusFilter === statusKey;
            return (
              <button
                key={statusKey}
                type="button"
                onClick={() => handleQuickFilter(statusKey as DocumentQuickFilter)}
                className={[
                  "rounded-xl border p-4 text-left transition",
                  active
                    ? "border-blue-400 ring-2 ring-blue-200 dark:border-blue-600 dark:ring-blue-900/40"
                    : "border-zinc-200 hover:border-zinc-300 dark:border-zinc-800 dark:hover:border-zinc-700",
                  "bg-white dark:bg-zinc-950",
                ].join(" ")}
              >
                <div className="text-xs text-zinc-600 dark:text-zinc-400">{meta.label}</div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
                    {statusCounts[statusKey] ?? 0}
                  </span>
                  <span
                    className={`inline-flex rounded-md px-1.5 py-0.5 text-[10px] font-medium ${meta.className}`}
                  >
                    {meta.label}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      ) : null}

      {!unavailable ? (
        <div className="flex flex-wrap items-end gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Статус
            </label>
            <select
              value={statusFilter}
              onChange={(e) => handleStatusDropdown(e.target.value)}
              className="min-w-[10rem] rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            >
              {STATUS_FILTER_OPTIONS.map((opt) => (
                <option key={opt.value || "all"} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Тип документа
            </label>
            <select
              value={documentFilter}
              onChange={(e) => setDocumentFilter(e.target.value)}
              className="min-w-[12rem] rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            >
              <option value="">Все типы</option>
              {documentTypes.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </div>
          <div className="min-w-[14rem] flex-1">
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Поиск сотрудника
            </label>
            <input
              type="search"
              value={employeeSearch}
              onChange={(e) => setEmployeeSearch(e.target.value)}
              placeholder="ФИО сотрудника"
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            />
          </div>
          <div className="text-sm text-zinc-500 dark:text-zinc-400">
            {loading ? "Загрузка…" : `${filteredItems.length} из ${items.length}`}
          </div>
        </div>
      ) : null}

      {!unavailable ? (
        <div className="flex flex-wrap gap-2">
          {DOCUMENT_QUICK_FILTERS.map((chip) => {
            const active = quickFilter === chip.value;
            return (
              <button
                key={chip.value || "all"}
                type="button"
                onClick={() => handleQuickFilter(chip.value)}
                className={[
                  "rounded-full border px-3 py-1.5 text-sm font-medium transition",
                  active
                    ? "border-blue-600 bg-blue-600 text-white"
                    : "border-zinc-300 bg-white text-zinc-800 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200 dark:hover:bg-zinc-900",
                ].join(" ")}
              >
                {chip.label}
              </button>
            );
          })}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr className="bg-zinc-100 text-left dark:bg-zinc-900">
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Сотрудник
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Основная специальность
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Квалификационная категория
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Тип документа
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Действует до
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Статус
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={tableColSpan} className="px-3 py-8 text-center text-zinc-500">
                    Загрузка…
                  </td>
                </tr>
              ) : null}
              {!loading && !unavailable && filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={tableColSpan} className="px-3 py-8 text-center text-zinc-500">
                    {items.length === 0
                      ? "Нет данных для демонстрации. Выполните локальный demo seed."
                      : "Записи не найдены по выбранным фильтрам"}
                  </td>
                </tr>
              ) : null}
              {!loading
                ? filteredItems.map((row, idx) => {
                    const meta = statusMeta(row.status);
                    return (
                      <tr
                        key={`${row.employee_id}-${row.certificate_type_name}-${idx}`}
                        onClick={() => {
                          setDrawerEmployeeId(String(row.employee_id));
                          setDrawerOpen(true);
                        }}
                        className="cursor-pointer border-t border-zinc-200 hover:bg-blue-50/60 dark:border-zinc-800 dark:hover:bg-blue-950/20"
                      >
                        <td className="px-3 py-2 font-medium text-zinc-900 dark:text-zinc-50">
                          {row.employee_name || `#${row.employee_id}`}
                        </td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                          {row.mainSpecialty}
                        </td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                          {row.category}
                        </td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                          {row.certificate_type_name}
                        </td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                          {fmtProfileDate(row.expires_at)}
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${meta.className}`}
                          >
                            {meta.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                : null}
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
