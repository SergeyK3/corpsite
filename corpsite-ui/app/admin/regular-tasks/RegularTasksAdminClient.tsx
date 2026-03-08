// FILE: corpsite-ui/app/admin/regular-tasks/RegularTasksAdminClient.tsx
"use client";

import * as React from "react";
import { apiFetchJson } from "../../../lib/api";

type RegularTaskItem = {
  regular_task_id: number;
  code: string;
  title: string;
  periodicity?: string | null;
  schedule_type?: string | null;
  executor_role_id?: number | null;
  assignment_scope?: string | null;
  is_active: boolean;
};

type RegularTasksListResponse = {
  total?: number;
  limit?: number;
  offset?: number;
  items?: RegularTaskItem[];
};

type RunStats = {
  templates_total?: number;
  templates_due?: number;
  created?: number;
  deduped?: number;
  errors?: number;
};

type RegularTaskRun = {
  run_id: number;
  started_at: string;
  finished_at?: string | null;
  status: string;
  stats?: RunStats | null;
  errors?: unknown;
};

type RunItem = {
  item_id: number;
  run_id: number;
  regular_task_id: number;
  status: string;
  started_at: string;
  finished_at?: string | null;
  period_id?: number | null;
  executor_role_id?: number | null;
  is_due: boolean;
  created_tasks: number;
  error?: string | null;
};

type RunResult = {
  run_id: number;
  dry_run: boolean;
  stats: RunStats;
};

type MainTab = "templates" | "runs";

function fmtDateTime(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("ru-RU");
}

function yesNo(value: boolean): string {
  return value ? "Да" : "Нет";
}

function statTone(status: string): string {
  const s = String(status || "").toLowerCase();
  if (s === "ok") return "text-emerald-300";
  if (s === "partial") return "text-amber-300";
  if (s === "error") return "text-red-300";
  if (s === "skip") return "text-zinc-300";
  return "text-zinc-200";
}

function scheduleLabel(item: RegularTaskItem): string {
  return item.schedule_type ?? item.periodicity ?? "—";
}

export default function RegularTasksAdminClient() {
  const [activeTab, setActiveTab] = React.useState<MainTab>("templates");

  const [templates, setTemplates] = React.useState<RegularTaskItem[]>([]);
  const [templatesLoading, setTemplatesLoading] = React.useState(false);
  const [templatesError, setTemplatesError] = React.useState<string | null>(null);

  const [runs, setRuns] = React.useState<RegularTaskRun[]>([]);
  const [runsLoading, setRunsLoading] = React.useState(false);
  const [runsError, setRunsError] = React.useState<string | null>(null);

  const [selectedRunId, setSelectedRunId] = React.useState<number | null>(null);
  const [runItems, setRunItems] = React.useState<RunItem[]>([]);
  const [runItemsLoading, setRunItemsLoading] = React.useState(false);
  const [runItemsError, setRunItemsError] = React.useState<string | null>(null);

  const [query, setQuery] = React.useState("");
  const [activeFilter, setActiveFilter] = React.useState<"all" | "active" | "inactive">("all");

  const [runAtLocalIso, setRunAtLocalIso] = React.useState("");
  const [dryRun, setDryRun] = React.useState(true);
  const [runSubmitting, setRunSubmitting] = React.useState(false);
  const [runSubmitError, setRunSubmitError] = React.useState<string | null>(null);
  const [lastRunResult, setLastRunResult] = React.useState<RunResult | null>(null);

  const loadTemplates = React.useCallback(async () => {
    setTemplatesLoading(true);
    setTemplatesError(null);
    try {
      const data = await apiFetchJson<RegularTasksListResponse>("/regular-tasks");
      setTemplates(Array.isArray(data?.items) ? data.items : []);
    } catch (err) {
      setTemplatesError(err instanceof Error ? err.message : "Не удалось загрузить шаблоны.");
      setTemplates([]);
    } finally {
      setTemplatesLoading(false);
    }
  }, []);

  const loadRuns = React.useCallback(async () => {
    setRunsLoading(true);
    setRunsError(null);
    try {
      const data = await apiFetchJson<RegularTaskRun[]>("/regular-task-runs");
      const rows = Array.isArray(data) ? data : [];
      setRuns(rows);
      if (rows.length > 0 && selectedRunId == null) {
        setSelectedRunId(rows[0].run_id);
      }
    } catch (err) {
      setRunsError(err instanceof Error ? err.message : "Не удалось загрузить историю запусков.");
      setRuns([]);
    } finally {
      setRunsLoading(false);
    }
  }, [selectedRunId]);

  const loadRunItems = React.useCallback(async (runId: number) => {
    setRunItemsLoading(true);
    setRunItemsError(null);
    try {
      const data = await apiFetchJson<RunItem[]>(`/regular-task-runs/${runId}/items`);
      setRunItems(Array.isArray(data) ? data : []);
    } catch (err) {
      setRunItemsError(err instanceof Error ? err.message : "Не удалось загрузить детали запуска.");
      setRunItems([]);
    } finally {
      setRunItemsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void loadTemplates();
    void loadRuns();
  }, [loadTemplates, loadRuns]);

  React.useEffect(() => {
    if (selectedRunId == null) {
      setRunItems([]);
      return;
    }
    void loadRunItems(selectedRunId);
  }, [selectedRunId, loadRunItems]);

  const filteredTemplates = React.useMemo(() => {
    const q = query.trim().toLowerCase();

    return templates.filter((item) => {
      if (activeFilter === "active" && !item.is_active) return false;
      if (activeFilter === "inactive" && item.is_active) return false;

      if (!q) return true;

      const haystack = [
        String(item.regular_task_id),
        item.code ?? "",
        item.title ?? "",
        item.schedule_type ?? "",
        item.assignment_scope ?? "",
        item.executor_role_id != null ? String(item.executor_role_id) : "",
      ]
        .join(" ")
        .toLowerCase();

      return haystack.includes(q);
    });
  }, [templates, query, activeFilter]);

  async function handleRunSubmit() {
    setRunSubmitting(true);
    setRunSubmitError(null);
    setLastRunResult(null);

    try {
      const payload: Record<string, unknown> = {
        dry_run: dryRun,
      };

      if (runAtLocalIso.trim()) {
        payload.run_at_local_iso = runAtLocalIso.trim();
      }

      const result = await apiFetchJson<RunResult>("/internal/regular-tasks/run", {
        method: "POST",
        body: JSON.stringify(payload),
        headers: {
          "Content-Type": "application/json",
        },
      });

      setLastRunResult(result);
      setActiveTab("runs");
      await loadRuns();
      if (result?.run_id) {
        setSelectedRunId(result.run_id);
      }
    } catch (err) {
      setRunSubmitError(err instanceof Error ? err.message : "Не удалось выполнить запуск.");
    } finally {
      setRunSubmitting(false);
    }
  }

  async function handleRefreshAll() {
    await Promise.all([loadTemplates(), loadRuns()]);
    if (selectedRunId != null) {
      await loadRunItems(selectedRunId);
    }
  }

  return (
    <div className="flex flex-col gap-4 text-zinc-100">
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">Техадмин · Регулярные задачи</h1>
            <p className="mt-1 text-sm text-zinc-400">
              Шаблоны, история запусков и пробный запуск генератора регулярных задач.
            </p>
          </div>

          <div className="flex flex-col gap-3 md:flex-row md:items-end">
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-zinc-300">run_at_local_iso</label>
              <input
                className="w-[240px] rounded-xl border border-zinc-700 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-zinc-500"
                placeholder="2026-03-08T10:00:00"
                value={runAtLocalIso}
                onChange={(e) => setRunAtLocalIso(e.target.value)}
              />
            </div>

            <label className="flex items-center gap-2 rounded-xl border border-zinc-700 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-200">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
              />
              dry_run
            </label>

            <button
              type="button"
              onClick={handleRunSubmit}
              disabled={runSubmitting}
              className="rounded-2xl border border-zinc-700 bg-zinc-950/60 px-4 py-2 text-sm font-medium text-zinc-100 transition hover:bg-zinc-900 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {runSubmitting ? "Запуск..." : dryRun ? "Пробный запуск" : "Боевой запуск"}
            </button>

            <button
              type="button"
              onClick={handleRefreshAll}
              className="rounded-2xl border border-zinc-700 bg-zinc-950/60 px-4 py-2 text-sm font-medium text-zinc-100 transition hover:bg-zinc-900"
            >
              Обновить
            </button>
          </div>
        </div>

        {(runSubmitError || lastRunResult) && (
          <div className="mt-4 rounded-2xl border border-zinc-800 bg-zinc-950/50 p-3 text-sm">
            {runSubmitError ? (
              <div className="text-red-300">{runSubmitError}</div>
            ) : lastRunResult ? (
              <div className="grid gap-1 md:grid-cols-4">
                <div>
                  <span className="font-medium text-zinc-300">run_id:</span> {lastRunResult.run_id}
                </div>
                <div>
                  <span className="font-medium text-zinc-300">templates_due:</span>{" "}
                  {lastRunResult.stats?.templates_due ?? 0}
                </div>
                <div>
                  <span className="font-medium text-zinc-300">created:</span> {lastRunResult.stats?.created ?? 0}
                </div>
                <div>
                  <span className="font-medium text-zinc-300">errors:</span> {lastRunResult.stats?.errors ?? 0}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 shadow-sm">
        <div className="mb-4 flex flex-wrap gap-2 border-b border-zinc-800 pb-3">
          <button
            type="button"
            onClick={() => setActiveTab("templates")}
            className={[
              "rounded-t-xl border px-4 py-2 text-sm font-medium transition",
              activeTab === "templates"
                ? "border-zinc-700 bg-zinc-950 text-zinc-100"
                : "border-zinc-800 bg-zinc-900/30 text-zinc-400 hover:bg-zinc-900/50 hover:text-zinc-200",
            ].join(" ")}
          >
            Шаблоны
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("runs")}
            className={[
              "rounded-t-xl border px-4 py-2 text-sm font-medium transition",
              activeTab === "runs"
                ? "border-zinc-700 bg-zinc-950 text-zinc-100"
                : "border-zinc-800 bg-zinc-900/30 text-zinc-400 hover:bg-zinc-900/50 hover:text-zinc-200",
            ].join(" ")}
          >
            Запуски
          </button>
        </div>

        {activeTab === "templates" ? (
          <section>
            <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-zinc-100">Шаблоны регулярных задач</h2>
                <p className="text-sm text-zinc-400">Всего: {filteredTemplates.length}</p>
              </div>

              <div className="flex flex-col gap-2 md:flex-row">
                <input
                  className="w-full rounded-xl border border-zinc-700 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-zinc-500 md:w-[260px]"
                  placeholder="Поиск по коду, названию, роли, области..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <select
                  className="rounded-xl border border-zinc-700 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-100 outline-none transition focus:border-zinc-500"
                  value={activeFilter}
                  onChange={(e) => setActiveFilter(e.target.value as "all" | "active" | "inactive")}
                >
                  <option value="all">Все</option>
                  <option value="active">Только активные</option>
                  <option value="inactive">Только неактивные</option>
                </select>
              </div>
            </div>

            {templatesLoading ? (
              <div className="rounded-xl border border-dashed border-zinc-700 p-6 text-sm text-zinc-500">
                Загрузка шаблонов...
              </div>
            ) : templatesError ? (
              <div className="rounded-xl border border-red-900/60 bg-red-950/40 p-4 text-sm text-red-300">
                {templatesError}
              </div>
            ) : (
              <div className="overflow-auto rounded-2xl border border-zinc-800">
                <table className="min-w-full table-fixed text-sm">
                  <thead className="bg-zinc-900 text-left">
                    <tr>
                      <th className="w-[64px] px-3 py-2 font-medium text-zinc-300">ID</th>
                      <th className="w-[170px] px-3 py-2 font-medium text-zinc-300">Код</th>
                      <th className="px-3 py-2 font-medium text-zinc-300">Отчет</th>
                      <th className="w-[130px] px-3 py-2 font-medium text-zinc-300">Расписание</th>
                      <th className="w-[110px] px-3 py-2 font-medium text-zinc-300">Исполнитель</th>
                      <th className="w-[120px] px-3 py-2 font-medium text-zinc-300">Область</th>
                      <th className="w-[90px] px-3 py-2 font-medium text-zinc-300">Активен</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTemplates.map((item) => (
                      <tr key={item.regular_task_id} className="border-t border-zinc-800 align-top hover:bg-zinc-900/50">
                        <td className="px-3 py-2 text-zinc-200">{item.regular_task_id}</td>
                        <td className="break-all px-3 py-2 font-mono text-xs text-zinc-400">{item.code}</td>
                        <td className="px-3 py-2 text-zinc-100">{item.title}</td>
                        <td className="px-3 py-2 text-zinc-300">{scheduleLabel(item)}</td>
                        <td className="px-3 py-2 text-zinc-300">{item.executor_role_id ?? "—"}</td>
                        <td className="px-3 py-2 text-zinc-300">{item.assignment_scope ?? "—"}</td>
                        <td className="px-3 py-2">
                          <span
                            className={[
                              "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                              item.is_active
                                ? "bg-emerald-950/60 text-emerald-300"
                                : "bg-zinc-800 text-zinc-300",
                            ].join(" ")}
                          >
                            {item.is_active ? "Да" : "Нет"}
                          </span>
                        </td>
                      </tr>
                    ))}
                    {filteredTemplates.length === 0 && (
                      <tr>
                        <td colSpan={7} className="px-3 py-6 text-center text-zinc-500">
                          Нет данных.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        ) : (
          <section className="flex flex-col gap-4">
            <div>
              <h2 className="text-lg font-semibold text-zinc-100">История запусков</h2>
              <p className="text-sm text-zinc-400">Последние 100 запусков</p>
            </div>

            {runsLoading ? (
              <div className="rounded-xl border border-dashed border-zinc-700 p-6 text-sm text-zinc-500">
                Загрузка истории запусков...
              </div>
            ) : runsError ? (
              <div className="rounded-xl border border-red-900/60 bg-red-950/40 p-4 text-sm text-red-300">
                {runsError}
              </div>
            ) : (
              <div className="overflow-auto rounded-2xl border border-zinc-800">
                <table className="min-w-full table-fixed text-sm">
                  <thead className="bg-zinc-900 text-left">
                    <tr>
                      <th className="w-[80px] px-3 py-2 font-medium text-zinc-300">Запуск</th>
                      <th className="w-[170px] px-3 py-2 font-medium text-zinc-300">Старт</th>
                      <th className="w-[100px] px-3 py-2 font-medium text-zinc-300">Статус</th>
                      <th className="w-[100px] px-3 py-2 font-medium text-zinc-300">Создано</th>
                      <th className="w-[110px] px-3 py-2 font-medium text-zinc-300">Дедупл.</th>
                      <th className="w-[90px] px-3 py-2 font-medium text-zinc-300">Ошибки</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => {
                      const selected = selectedRunId === run.run_id;
                      return (
                        <tr
                          key={run.run_id}
                          className={[
                            "cursor-pointer border-t border-zinc-800",
                            selected ? "bg-zinc-800/80" : "hover:bg-zinc-900/50",
                          ].join(" ")}
                          onClick={() => setSelectedRunId(run.run_id)}
                        >
                          <td className="px-3 py-2 font-medium text-zinc-100">{run.run_id}</td>
                          <td className="px-3 py-2 text-zinc-300">{fmtDateTime(run.started_at)}</td>
                          <td className={`px-3 py-2 ${statTone(run.status)}`}>{run.status}</td>
                          <td className="px-3 py-2 text-zinc-300">{run.stats?.created ?? 0}</td>
                          <td className="px-3 py-2 text-zinc-300">{run.stats?.deduped ?? 0}</td>
                          <td className="px-3 py-2 text-zinc-300">{run.stats?.errors ?? 0}</td>
                        </tr>
                      );
                    })}
                    {runs.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-3 py-6 text-center text-zinc-500">
                          Нет запусков.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            <div className="rounded-2xl border border-zinc-800 bg-zinc-950/40 p-4">
              <div className="mb-3">
                <h3 className="text-base font-semibold text-zinc-100">Детализация запуска</h3>
                <p className="text-sm text-zinc-400">
                  {selectedRunId != null ? `run_id = ${selectedRunId}` : "Запуск не выбран"}
                </p>
              </div>

              {selectedRunId == null ? (
                <div className="rounded-xl border border-dashed border-zinc-700 p-6 text-sm text-zinc-500">
                  Выбери запуск в таблице выше.
                </div>
              ) : runItemsLoading ? (
                <div className="rounded-xl border border-dashed border-zinc-700 p-6 text-sm text-zinc-500">
                  Загрузка деталей...
                </div>
              ) : runItemsError ? (
                <div className="rounded-xl border border-red-900/60 bg-red-950/40 p-4 text-sm text-red-300">
                  {runItemsError}
                </div>
              ) : (
                <div className="overflow-auto rounded-2xl border border-zinc-800">
                  <table className="min-w-full table-fixed text-sm">
                    <thead className="bg-zinc-900 text-left">
                      <tr>
                        <th className="w-[90px] px-3 py-2 font-medium text-zinc-300">Шаблон</th>
                        <th className="w-[90px] px-3 py-2 font-medium text-zinc-300">Период</th>
                        <th className="w-[120px] px-3 py-2 font-medium text-zinc-300">Исполнитель</th>
                        <th className="w-[90px] px-3 py-2 font-medium text-zinc-300">Актуален</th>
                        <th className="w-[90px] px-3 py-2 font-medium text-zinc-300">Создано</th>
                        <th className="w-[100px] px-3 py-2 font-medium text-zinc-300">Статус</th>
                        <th className="px-3 py-2 font-medium text-zinc-300">Ошибка</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runItems.map((item) => (
                        <tr key={item.item_id} className="border-t border-zinc-800 align-top hover:bg-zinc-900/50">
                          <td className="px-3 py-2 text-zinc-200">{item.regular_task_id}</td>
                          <td className="px-3 py-2 text-zinc-300">{item.period_id ?? "—"}</td>
                          <td className="px-3 py-2 text-zinc-300">{item.executor_role_id ?? "—"}</td>
                          <td className="px-3 py-2 text-zinc-300">{yesNo(item.is_due)}</td>
                          <td className="px-3 py-2 text-zinc-300">{item.created_tasks}</td>
                          <td className={`px-3 py-2 ${statTone(item.status)}`}>{item.status}</td>
                          <td className="px-3 py-2 text-xs text-red-300">{item.error ?? "—"}</td>
                        </tr>
                      ))}
                      {runItems.length === 0 && (
                        <tr>
                          <td colSpan={7} className="px-3 py-6 text-center text-zinc-500">
                            Нет элементов запуска.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}