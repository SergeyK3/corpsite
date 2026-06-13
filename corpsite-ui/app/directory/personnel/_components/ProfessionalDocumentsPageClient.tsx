// FILE: corpsite-ui/app/directory/personnel/_components/ProfessionalDocumentsPageClient.tsx
"use client";

import * as React from "react";

import EmployeeDrawer from "../../employees/_components/EmployeeDrawer";
import PersonnelSubNav from "./PersonnelSubNav";
import {
  listProfessionalDocuments,
  mapDemoApiError,
  type ProfessionalDocumentRow,
} from "../_lib/demoApi.client";

const STATUS_META: Record<
  string,
  { label: string; className: string }
> = {
  VALID: {
    label: "Действует",
    className: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-200",
  },
  EXPIRING_60: {
    label: "≤ 60 дней",
    className: "bg-yellow-100 text-yellow-900 dark:bg-yellow-950/40 dark:text-yellow-200",
  },
  EXPIRING_30: {
    label: "≤ 30 дней",
    className: "bg-orange-100 text-orange-900 dark:bg-orange-950/40 dark:text-orange-200",
  },
  EXPIRED: {
    label: "Истёк",
    className: "bg-red-100 text-red-900 dark:bg-red-950/50 dark:text-red-200",
  },
  MISSING: {
    label: "Нет данных",
    className: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  },
};

function fmtDate(v: string | null | undefined): string {
  if (!v) return "—";
  const dt = new Date(v);
  if (Number.isNaN(dt.getTime())) return v;
  return dt.toLocaleDateString("ru-RU");
}

export default function ProfessionalDocumentsPageClient() {
  const [items, setItems] = React.useState<ProfessionalDocumentRow[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [unavailable, setUnavailable] = React.useState(false);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerEmployeeId, setDrawerEmployeeId] = React.useState<string | null>(null);

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

  function statusMeta(status: string) {
    return (
      STATUS_META[status] ?? {
        label: status,
        className: "bg-zinc-100 text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200",
      }
    );
  }

  return (
    <div className="space-y-4">
      <PersonnelSubNav />

      <div>
        <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
          Профессиональные документы
        </h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Демонстрация контроля сроков (ADR-034 demo)
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

      <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr className="bg-zinc-100 text-left dark:bg-zinc-900">
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Сотрудник
                </th>
                <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400">
                  Документ
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
                  <td colSpan={4} className="px-3 py-8 text-center text-zinc-500">
                    Загрузка…
                  </td>
                </tr>
              ) : null}
              {!loading && !unavailable && items.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-3 py-8 text-center text-zinc-500">
                    Нет данных для демонстрации. Выполните локальный demo seed.
                  </td>
                </tr>
              ) : null}
              {!loading
                ? items.map((row, idx) => {
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
                          {row.certificate_type_name}
                        </td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                          {fmtDate(row.expires_at)}
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
