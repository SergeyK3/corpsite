"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import TaskOrgFiltersBar from "@/components/TaskOrgFiltersBar";
import { buildPersonalCardHref } from "@/lib/employeeCardNav";
import PersonnelSubNav from "./PersonnelSubNav";
import {
  bulkAssignOnboardingTasks,
  bulkCompleteOnboardingTasks,
  bulkUpdateOnboardingDueDates,
  listOnboardingTasks,
  mapEmployeeOnboardingApiError,
  onboardingChecklistStatusLabel,
  onboardingPriorityLabel,
  type OnboardingTaskListItem,
} from "../_lib/employeeOnboardingApi.client";

const BASE_PATH = "/directory/personnel/onboarding/tasks";

export default function OnboardingTasksJournalPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [items, setItems] = React.useState<OnboardingTaskListItem[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [busy, setBusy] = React.useState(false);
  const [searchDraft, setSearchDraft] = React.useState(searchParams.get("q") || "");

  const q = searchParams.get("q") || "";
  const status = searchParams.get("status") || "";
  const overdueOnly = searchParams.get("overdue_only") === "1";
  const limit = Number(searchParams.get("limit") || 50);
  const offset = Number(searchParams.get("offset") || 0);
  const orgUnitIdRaw = searchParams.get("org_unit_id");
  const orgUnitId = orgUnitIdRaw ? Number(orgUnitIdRaw) : undefined;

  React.useEffect(() => {
    setSearchDraft(q);
  }, [q]);

  const reload = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await listOnboardingTasks({
        q: q || undefined,
        status: status || undefined,
        org_unit_id: orgUnitId,
        overdue_only: overdueOnly || undefined,
        limit,
        offset,
      });
      setItems(body.items);
      setTotal(body.total);
      setSelected(new Set());
    } catch (e) {
      setItems([]);
      setTotal(0);
      setError(mapEmployeeOnboardingApiError(e, "Не удалось загрузить журнал задач"));
    } finally {
      setLoading(false);
    }
  }, [q, status, orgUnitId, overdueOnly, limit, offset]);

  React.useEffect(() => {
    void reload();
  }, [reload]);

  function replaceParams(next: Record<string, string | number | null | undefined>) {
    const params = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(next)) {
      if (value == null || value === "") params.delete(key);
      else params.set(key, String(value));
    }
    const qs = params.toString();
    router.replace(qs ? `${BASE_PATH}?${qs}` : BASE_PATH);
  }

  function toggleSelected(itemId: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  }

  async function runBulk(action: "assign" | "due-date" | "complete") {
    const itemIds = Array.from(selected);
    if (itemIds.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      if (action === "assign") {
        await bulkAssignOnboardingTasks({ item_ids: itemIds, assignee_kind: "hr" });
      } else if (action === "due-date") {
        const iso = new Date(Date.now() + 7 * 86400000).toISOString();
        await bulkUpdateOnboardingDueDates({ item_ids: itemIds, due_date: iso });
      } else {
        await bulkCompleteOnboardingTasks({ item_ids: itemIds });
      }
      await reload();
    } catch (e) {
      setError(mapEmployeeOnboardingApiError(e, "Не удалось выполнить массовую операцию"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4 p-4" data-testid="onboarding-tasks-journal-page">
      <PersonnelSubNav />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Журнал задач адаптации</h1>
          <p className="mt-1 text-sm text-zinc-500">Все задачи активных программ адаптации.</p>
        </div>
        <Link
          href="/directory/personnel/onboarding/dashboard"
          className="text-sm text-blue-700 hover:underline dark:text-blue-300"
        >
          Dashboard
        </Link>
      </div>

      <TaskOrgFiltersBar basePath={BASE_PATH} className="rounded-xl border border-zinc-200 p-3 dark:border-zinc-800" />

      <div className="flex flex-wrap items-end gap-3">
        <label className="block min-w-[14rem] flex-1 text-sm">
          <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Поиск по сотруднику</span>
          <input
            value={searchDraft}
            onChange={(e) => setSearchDraft(e.target.value)}
            placeholder="ФИО, № сотрудника"
            className="w-full rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
            data-testid="onboarding-tasks-search"
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
            data-testid="onboarding-tasks-status-filter"
          >
            <option value="">Все</option>
            <option value="pending">Ожидает</option>
            <option value="completed">Выполнено</option>
            <option value="skipped">Пропущено</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={overdueOnly}
            onChange={(e) => replaceParams({ overdue_only: e.target.checked ? "1" : null, offset: 0 })}
            data-testid="onboarding-tasks-overdue-filter"
          />
          Только просроченные
        </label>
      </div>

      {selected.size > 0 ? (
        <div className="flex flex-wrap gap-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <span className="text-sm text-zinc-600 dark:text-zinc-400">Выбрано: {selected.size}</span>
          <button
            type="button"
            disabled={busy}
            className="rounded-lg border px-3 py-1 text-sm dark:border-zinc-700"
            data-testid="onboarding-bulk-assign-hr"
            onClick={() => void runBulk("assign")}
          >
            Назначить HR
          </button>
          <button
            type="button"
            disabled={busy}
            className="rounded-lg border px-3 py-1 text-sm dark:border-zinc-700"
            data-testid="onboarding-bulk-due-date"
            onClick={() => void runBulk("due-date")}
          >
            Срок +7 дней
          </button>
          <button
            type="button"
            disabled={busy}
            className="rounded-lg border px-3 py-1 text-sm dark:border-zinc-700"
            data-testid="onboarding-bulk-complete"
            onClick={() => void runBulk("complete")}
          >
            Отметить выполненными
          </button>
        </div>
      ) : null}

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div data-testid="onboarding-tasks-loading" className="h-20 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />
      ) : items.length === 0 ? (
        <div data-testid="onboarding-tasks-empty" className="rounded-xl border border-dashed px-4 py-10 text-center text-sm text-zinc-500">
          Задач не найдено.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800" data-testid="onboarding-tasks-table">
          <table className="min-w-full divide-y divide-zinc-200 text-sm dark:divide-zinc-800">
            <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900/60">
              <tr>
                <th className="px-4 py-3" />
                <th className="px-4 py-3">Задача</th>
                <th className="px-4 py-3">Сотрудник</th>
                <th className="px-4 py-3">Подразделение</th>
                <th className="px-4 py-3">Срок</th>
                <th className="px-4 py-3">Приоритет</th>
                <th className="px-4 py-3">Статус</th>
                <th className="px-4 py-3">Ответственный</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100 dark:divide-zinc-900">
              {items.map((item) => (
                <tr key={item.item_id} className={item.is_overdue ? "bg-red-50/60 dark:bg-red-950/20" : undefined}>
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(item.item_id)}
                      onChange={() => toggleSelected(item.item_id)}
                      data-testid={`onboarding-task-select-${item.item_id}`}
                    />
                  </td>
                  <td className="px-4 py-3">{item.title}</td>
                  <td className="px-4 py-3">
                    <Link
                      href={buildPersonalCardHref({ employeeId: item.employee_id }, { section: "onboarding" })}
                      className="font-medium text-blue-700 hover:underline dark:text-blue-300"
                    >
                      {item.employee_full_name || `#${item.employee_id}`}
                    </Link>
                  </td>
                  <td className="px-4 py-3">{item.org_unit_name || "—"}</td>
                  <td className="px-4 py-3">
                    {item.due_date ? new Date(item.due_date).toLocaleDateString("ru-RU") : "—"}
                    {item.is_overdue ? (
                      <span className="ml-2 text-xs font-medium text-red-700 dark:text-red-300">просрочено</span>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">{onboardingPriorityLabel(item.priority)}</td>
                  <td className="px-4 py-3">{onboardingChecklistStatusLabel(item.status)}</td>
                  <td className="px-4 py-3">{item.assignee_name || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading ? (
        <div className="text-sm text-zinc-500" data-testid="onboarding-tasks-total">
          Всего: {total}
        </div>
      ) : null}
    </div>
  );
}
