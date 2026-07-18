"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { buildPersonalCardHref } from "@/lib/employeeCardNav";
import TaskOrgFiltersBar from "@/components/TaskOrgFiltersBar";
import {
  listEmployeeOnboardings,
  mapEmployeeOnboardingApiError,
  onboardingStatusLabel,
  type EmployeeOnboardingListItem,
} from "../_lib/employeeOnboardingApi.client";

const BASE_PATH = "/directory/personnel/onboarding";

export default function EmployeeOnboardingJournalPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [items, setItems] = React.useState<EmployeeOnboardingListItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [searchDraft, setSearchDraft] = React.useState(searchParams.get("q") || "");
  const q = searchParams.get("q") || "";
  const status = searchParams.get("status") || "";
  const sort = searchParams.get("sort") || "started_at_desc";
  const limit = Number(searchParams.get("limit") || 50);
  const offset = Number(searchParams.get("offset") || 0);
  const orgUnitIdRaw = searchParams.get("org_unit_id");
  const orgUnitId = orgUnitIdRaw ? Number(orgUnitIdRaw) : undefined;

  React.useEffect(() => {
    setSearchDraft(q);
  }, [q]);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void listEmployeeOnboardings({
      q: q || undefined,
      status: status || undefined,
      sort,
      limit,
      offset,
      org_unit_id: orgUnitId,
    })
      .then((body) => {
        if (!cancelled) {
          setItems(body.items);
          setTotal(body.total);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setItems([]);
          setTotal(0);
          setError(mapEmployeeOnboardingApiError(e, "Не удалось загрузить журнал адаптации"));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [q, status, sort, limit, offset, orgUnitId]);

  function replaceParams(next: Record<string, string | number | null | undefined>) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(next)) {
      if (value == null || value === "") params.delete(key);
      else params.set(key, String(value));
    }
    const qs = params.toString();
    router.replace(qs ? `${BASE_PATH}?${qs}` : BASE_PATH);
  }

  return (
    <div className="space-y-4 p-4" data-testid="employee-onboarding-journal-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Журнал адаптации</h1>
          <p className="mt-1 text-sm text-zinc-500">Программы адаптации новых сотрудников после приёма на работу.</p>
        </div>
        <div className="flex gap-3 text-sm">
          <Link href="/directory/personnel/onboarding/dashboard" className="text-blue-700 hover:underline dark:text-blue-300">
            Dashboard
          </Link>
          <Link href="/directory/personnel/onboarding/tasks" className="text-blue-700 hover:underline dark:text-blue-300">
            Задачи
          </Link>
        </div>
      </div>

      <TaskOrgFiltersBar basePath={BASE_PATH} className="rounded-xl border border-zinc-200 p-3 dark:border-zinc-800" />

      <div className="flex flex-wrap items-end gap-3">
        <label className="block min-w-[14rem] flex-1 text-sm">
          <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Поиск</span>
          <input
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            placeholder="ФИО, № сотрудника"
            className="w-full rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
            data-testid="employee-onboarding-search"
            onKeyDown={(e) => {
              if (e.key === "Enter") replaceParams({ q: searchDraft.trim(), offset: 0 });
            }}
            onBlur={() => {
              if (searchDraft.trim() !== q) replaceParams({ q: searchDraft.trim(), offset: 0 });
            }}
          />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Статус</span>
          <select
            value={status}
            onChange={(e) => replaceParams({ status: e.target.value, offset: 0 })}
            className="rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
            data-testid="employee-onboarding-status-filter"
          >
            <option value="">Все</option>
            <option value="active">В процессе</option>
            <option value="completed">Завершена</option>
            <option value="cancelled">Отменена</option>
            <option value="planned">Запланирована</option>
          </select>
        </label>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div data-testid="employee-onboarding-journal-loading" className="h-20 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />
      ) : items.length === 0 ? (
        <div data-testid="employee-onboarding-journal-empty" className="rounded-xl border border-dashed px-4 py-10 text-center text-sm text-zinc-500">
          Записей адаптации пока нет.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800" data-testid="employee-onboarding-journal-table">
          <table className="min-w-full divide-y divide-zinc-200 text-sm dark:divide-zinc-800">
            <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900/60">
              <tr>
                <th className="px-4 py-3">Сотрудник</th>
                <th className="px-4 py-3">Подразделение</th>
                <th className="px-4 py-3">Статус</th>
                <th className="px-4 py-3">Прогресс</th>
                <th className="px-4 py-3">HR</th>
                <th className="px-4 py-3">Начало</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-900">
              {items.map((item) => (
                <tr key={item.onboarding_id}>
                  <td className="px-4 py-3">
                    <Link
                      href={buildPersonalCardHref({ employeeId: item.employee_id }, { section: "onboarding" })}
                      className="font-medium text-blue-700 hover:underline dark:text-blue-300"
                    >
                      {item.employee_full_name || `#${item.employee_id}`}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{item.org_unit_name || "—"}</td>
                  <td className="px-4 py-3">{onboardingStatusLabel(item.status)}</td>
                  <td className="px-4 py-3">{item.progress_percent}%</td>
                  <td className="px-4 py-3">{item.responsible_hr_name || `#${item.responsible_hr_id}`}</td>
                  <td className="px-4 py-3">{new Date(item.started_at).toLocaleDateString("ru-RU")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading ? (
        <div className="text-sm text-zinc-500" data-testid="employee-onboarding-journal-total">
          Всего: {total}
        </div>
      ) : null}
    </div>
  );
}
