"use client";

import * as React from "react";
import Link from "next/link";

import {
  getOnboardingDashboard,
  mapEmployeeOnboardingApiError,
  type OnboardingDashboard,
} from "../_lib/employeeOnboardingApi.client";
import { buildPersonalCardHref } from "@/lib/employeeCardNav";

const BASE_PATH = "/directory/personnel/onboarding";

function MetricCard({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
      <div className="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}

export default function OnboardingDashboardPageClient() {
  const [dashboard, setDashboard] = React.useState<OnboardingDashboard | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void getOnboardingDashboard()
      .then((data) => {
        if (!cancelled) setDashboard(data);
      })
      .catch((e) => {
        if (!cancelled) {
          setDashboard(null);
          setError(mapEmployeeOnboardingApiError(e, "Не удалось загрузить dashboard адаптации"));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-4 p-4" data-testid="onboarding-dashboard-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Dashboard адаптации</h1>
          <p className="mt-1 text-sm text-zinc-500">Сводка по активным программам и задачам.</p>
        </div>
        <div className="flex gap-2 text-sm">
          <Link href={`${BASE_PATH}/tasks`} className="text-blue-700 hover:underline dark:text-blue-300">
            Журнал задач
          </Link>
          <Link href={BASE_PATH} className="text-blue-700 hover:underline dark:text-blue-300">
            Журнал программ
          </Link>
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div data-testid="onboarding-dashboard-loading" className="h-24 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />
      ) : dashboard ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard label="Активные программы" value={dashboard.active_programs_count} />
            <MetricCard label="Просроченные задачи" value={dashboard.overdue_tasks_count} />
            <MetricCard label="Ближайшие сроки (3 дня)" value={dashboard.due_soon_tasks_count} />
            <MetricCard label="Завершено программ" value={`${dashboard.completion_percent}%`} />
          </div>

          <section className="space-y-2">
            <h2 className="text-lg font-semibold">Просроченные задачи</h2>
            {dashboard.overdue_tasks.length === 0 ? (
              <p className="text-sm text-zinc-500">Просрочек нет.</p>
            ) : (
              <TaskMiniTable items={dashboard.overdue_tasks} />
            )}
          </section>

          <section className="space-y-2">
            <h2 className="text-lg font-semibold">Ближайшие сроки</h2>
            {dashboard.due_soon_tasks.length === 0 ? (
              <p className="text-sm text-zinc-500">Задач с ближайшим сроком нет.</p>
            ) : (
              <TaskMiniTable items={dashboard.due_soon_tasks} />
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}

function TaskMiniTable({
  items,
}: {
  items: OnboardingDashboard["overdue_tasks"];
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
      <table className="min-w-full divide-y divide-zinc-200 text-sm dark:divide-zinc-800">
        <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900/60">
          <tr>
            <th className="px-4 py-3">Задача</th>
            <th className="px-4 py-3">Сотрудник</th>
            <th className="px-4 py-3">Срок</th>
            <th className="px-4 py-3">Ответственный</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100 dark:divide-zinc-900">
          {items.map((item) => (
            <tr key={item.item_id} data-testid={`onboarding-dashboard-task-${item.item_id}`}>
              <td className="px-4 py-3">{item.title}</td>
              <td className="px-4 py-3">
                <Link
                  href={buildPersonalCardHref({ employeeId: item.employee_id }, { section: "onboarding" })}
                  className="text-blue-700 hover:underline dark:text-blue-300"
                >
                  {item.employee_full_name || `#${item.employee_id}`}
                </Link>
              </td>
              <td className="px-4 py-3">
                {item.due_date ? new Date(item.due_date).toLocaleDateString("ru-RU") : "—"}
              </td>
              <td className="px-4 py-3">{item.assignee_name || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
