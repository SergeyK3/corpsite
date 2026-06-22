// FILE: corpsite-ui/app/regular-task-runs/_components/RegularTaskRunsJournalView.tsx
"use client";

import Link from "next/link";
import { useMemo } from "react";

import { runTitleLabel, translateRunIssueMessage, uiFieldLabel } from "@/lib/i18n";
import {
  buildItemOriginView,
  buildRunListEntry,
  buildRunSummary,
  itemOutcomeLabel,
  itemOutcomeTone,
  itemTitleLabel,
  periodLabel,
  resolveRunTaskListState,
  RUN_TASK_LIST_EXPECTED_NOT_LOADED_MESSAGE,
  roleLabel,
  type RegularTaskRunItemRow,
  type RegularTaskRunRow,
} from "@/lib/regularTaskRunJournal";

export type RegularTaskRunsJournalViewProps = {
  runs: RegularTaskRunRow[];
  runsLoading: boolean;
  runsError: string | null;
  selectedRunId: number | null;
  onSelectRun: (runId: number) => void;
  onRefreshRuns: () => void;
  items: RegularTaskRunItemRow[];
  itemsLoading: boolean;
  itemsError: string | null;
  onRefreshItems: () => void;
  onlyIssues: boolean;
  onOnlyIssuesChange: (value: boolean) => void;
  search: string;
  onSearchChange: (value: string) => void;
};

function runKindBadgeClass(runKind: string): string {
  if (runKind === "catch_up") {
    return "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200";
  }
  return "border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-200";
}

function runModeBadgeClass(runMode: string): string {
  if (runMode === "dry") {
    return "border-violet-200 bg-violet-50 text-violet-900 dark:border-violet-800 dark:bg-violet-950/40 dark:text-violet-200";
  }
  return "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200";
}

function statTone(status: string): string {
  const s = String(status || "").toLowerCase();
  if (s === "ok") return "text-emerald-800 dark:text-emerald-200";
  if (s === "partial") return "text-amber-900 dark:text-amber-200";
  if (s === "error") return "text-red-700 dark:text-red-300";
  if (s === "skip") return "text-zinc-700 dark:text-zinc-300";
  return "text-zinc-800 dark:text-zinc-200";
}

function yesNo(value: boolean): string {
  return value ? "Да" : "Нет";
}

function SummaryField({
  label,
  value,
  ...rest
}: {
  label: string;
  value: string;
} & React.ComponentPropsWithoutRef<"div">) {
  return (
    <div
      className="rounded-lg border border-zinc-200 bg-white p-2.5 dark:border-zinc-800 dark:bg-zinc-950"
      {...rest}
    >
      <div className="text-[11px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400">{label}</div>
      <div className="mt-1 text-sm font-medium text-zinc-900 dark:text-zinc-50">{value}</div>
    </div>
  );
}

function runTaskOutcomeTone(outcome: string): string {
  switch (outcome) {
    case "created":
      return "text-emerald-800 dark:text-emerald-200";
    case "dedup":
      return "text-amber-800 dark:text-amber-200";
    case "error":
      return "text-red-700 dark:text-red-300";
    case "skip":
      return "text-zinc-600 dark:text-zinc-400";
    default:
      return "text-zinc-800 dark:text-zinc-200";
  }
}

function OriginCompact({ item }: { item: RegularTaskRunItemRow }) {
  const origin = buildItemOriginView(item);
  return (
    <div className="space-y-0.5 text-[11px] leading-snug text-zinc-600 dark:text-zinc-400">
      <div>
        <span className="text-zinc-500 dark:text-zinc-500">Источник:</span> {origin.source_label}
      </div>
      {origin.origin_run_id ? (
        <div>
          <span className="text-zinc-500 dark:text-zinc-500">ID запуска:</span> {origin.origin_run_id}
        </div>
      ) : null}
      <div>
        <span className="text-zinc-500 dark:text-zinc-500">{uiFieldLabel("occurrence_date")}:</span>{" "}
        <span className="font-medium text-zinc-800 dark:text-zinc-200">{origin.occurrence_date_label}</span>
      </div>
      <div>
        <span className="text-zinc-500 dark:text-zinc-500">{uiFieldLabel("run_kind")}:</span> {origin.run_kind_label}
      </div>
      {origin.period_label !== "—" ? (
        <div>
          <span className="text-zinc-500 dark:text-zinc-500">{uiFieldLabel("period")}:</span> {origin.period_label}
        </div>
      ) : null}
    </div>
  );
}

export function resolveItemsEmptyMessage(
  items: readonly RegularTaskRunItemRow[],
  filteredItems: readonly RegularTaskRunItemRow[],
  onlyIssues: boolean,
  search: string,
): string | null {
  if (items.length === 0) return "Элементы отсутствуют.";
  if (filteredItems.length > 0) return null;
  if (onlyIssues) return "Ошибок нет.";
  if (search.trim()) return "По фильтру ничего не найдено.";
  return "Элементы отсутствуют.";
}

export function RegularTaskRunsJournalView({
  runs,
  runsLoading,
  runsError,
  selectedRunId,
  onSelectRun,
  onRefreshRuns,
  items,
  itemsLoading,
  itemsError,
  onRefreshItems,
  onlyIssues,
  onOnlyIssuesChange,
  search,
  onSearchChange,
}: RegularTaskRunsJournalViewProps) {
  const runEntries = useMemo(
    () =>
      runs.map((run) =>
        buildRunListEntry(run, run.run_id === selectedRunId ? items : []),
      ),
    [runs, selectedRunId, items],
  );

  const selectedRun = useMemo(() => {
    if (selectedRunId == null) return null;
    return runs.find((r) => r.run_id === selectedRunId) ?? null;
  }, [runs, selectedRunId]);

  const runSummary = useMemo(() => {
    if (!selectedRun) return null;
    return buildRunSummary(selectedRun, items);
  }, [selectedRun, items]);

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((it) => {
      if (onlyIssues && !String(it.error ?? "").trim()) return false;
      if (!q) return true;
      const hay = [
        it.item_id,
        it.regular_task_id,
        it.status,
        itemTitleLabel(it),
        roleLabel(it),
        periodLabel(it),
        itemOutcomeLabel(it),
        it.error ?? "",
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [items, onlyIssues, search]);

  const itemsEmptyMessage = resolveItemsEmptyMessage(items, filteredItems, onlyIssues, search);

  const taskListState = useMemo(() => {
    return resolveRunTaskListState(selectedRun, runSummary, items, itemsLoading);
  }, [selectedRun, runSummary, items, itemsLoading]);

  return (
    <div className="space-y-4" data-testid="regular-task-runs-journal">
      <header
        className="rounded-2xl border border-zinc-200 bg-white px-4 py-4 dark:border-zinc-800 dark:bg-zinc-900"
        data-testid="regular-task-runs-heading"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
              Журнал запусков регулярных задач
            </h1>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              История автоматических и догоняющих запусков регулярных задач.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/regular-tasks"
              className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-800 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200 dark:hover:bg-zinc-800"
            >
              Шаблоны
            </Link>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(260px,300px)_minmax(0,1fr)]">
        <section
          className="rounded-2xl border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900"
          data-testid="regular-task-runs-list-panel"
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Запуски</h2>
            <button
              type="button"
              onClick={onRefreshRuns}
              disabled={runsLoading}
              className="rounded-md border border-zinc-200 bg-white px-2.5 py-1.5 text-xs text-zinc-800 hover:bg-zinc-100 disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200"
            >
              {runsLoading ? "…" : "Обновить"}
            </button>
          </div>

          {runsError ? <div className="mb-2 text-xs text-red-700 dark:text-red-300">{runsError}</div> : null}
          {runsLoading ? <div className="text-sm text-zinc-600 dark:text-zinc-400">Загрузка…</div> : null}

          {!runsLoading && runs.length === 0 ? (
            <div className="rounded-lg border border-dashed border-zinc-300 p-4 text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
              Запусков нет.
            </div>
          ) : null}

          {!runsLoading && runs.length > 0 ? (
            <div
              className="max-h-[26rem] space-y-2 overflow-y-auto pr-1"
              data-testid="regular-task-runs-list-scroll"
            >
              {runEntries.map((entry) => {
                const active = selectedRunId === entry.run_id;
                return (
                  <button
                    key={entry.run_id}
                    type="button"
                    data-testid={`regular-task-run-card-${entry.run_id}`}
                    onClick={() => onSelectRun(entry.run_id)}
                    className={[
                      "w-full rounded-xl border px-3 py-2.5 text-left transition",
                      active
                        ? "border-zinc-400 bg-white shadow-sm dark:border-zinc-500 dark:bg-zinc-950"
                        : "border-zinc-200 bg-white hover:border-zinc-300 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-950 dark:hover:border-zinc-600",
                    ].join(" ")}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="font-medium text-zinc-900 dark:text-zinc-50">{entry.title}</div>
                      <span className={`text-xs font-medium ${statTone(entry.status)}`}>{entry.status_label}</span>
                    </div>

                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <span
                        className={[
                          "rounded-full border px-2 py-0.5 text-[11px] font-medium",
                          runKindBadgeClass(entry.run_kind),
                        ].join(" ")}
                      >
                        {entry.run_kind_label}
                      </span>
                      {entry.run_mode_label ? (
                        <span
                          className={[
                            "rounded-full border px-2 py-0.5 text-[11px] font-medium",
                            runModeBadgeClass(entry.run_mode ?? "live"),
                          ].join(" ")}
                          data-testid={`regular-task-run-mode-${entry.run_id}`}
                        >
                          {entry.run_mode_label}
                        </span>
                      ) : null}
                    </div>

                    <div className="mt-2 space-y-0.5 text-xs text-zinc-600 dark:text-zinc-400">
                      <div>
                        <span className="text-zinc-500">Дата запуска:</span> {entry.started_at_label}
                      </div>
                      <div>
                        <span className="text-zinc-500">{uiFieldLabel("occurrence_date")}:</span>{" "}
                        {entry.occurrence_date_label}
                      </div>
                      <div className="text-zinc-700 dark:text-zinc-300">{entry.counts_label}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          ) : null}
        </section>

        <div className="min-w-0 space-y-4">
          <section
            className="rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
            data-testid="regular-task-run-summary"
          >
            <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Сводка выбранного запуска</h2>

            {!selectedRun || !runSummary ? (
              <div className="mt-3 rounded-xl border border-dashed border-zinc-300 p-5 text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
                Выберите запуск в списке слева.
              </div>
            ) : (
              <div className="mt-3 space-y-3">
                {runSummary.journal_warning ? (
                  <div
                    className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100"
                    data-testid="regular-task-run-journal-warning"
                    role="alert"
                  >
                    {runSummary.journal_warning}
                  </div>
                ) : null}
                <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-4">
                <SummaryField label="Запуск" value={runTitleLabel(runSummary.run_id)} />
                <SummaryField label="Статус" value={runSummary.status_label} />
                <SummaryField label={uiFieldLabel("run_kind")} value={runSummary.run_kind_label} />
                {runSummary.run_mode_label ? (
                  <SummaryField
                    label="Режим"
                    value={runSummary.run_mode_label}
                    data-testid="regular-task-run-summary-mode"
                  />
                ) : null}
                <SummaryField label="Дата запуска" value={runSummary.started_at_label} />
                <SummaryField label={uiFieldLabel("occurrence_date")} value={runSummary.occurrence_date_label} />
                <SummaryField label={uiFieldLabel("period")} value={runSummary.period_label} />
                <SummaryField label={uiFieldLabel("schedule_type")} value={runSummary.schedule_type_label} />
                <SummaryField
                  label={`${uiFieldLabel("owner_unit")} / ${uiFieldLabel("org_group")}`}
                  value={runSummary.org_scope_label}
                />
                <SummaryField label="Шаблонов всего" value={String(runSummary.templates_total)} />
                <SummaryField label={uiFieldLabel("templates_due")} value={String(runSummary.templates_due)} />
                <SummaryField label={uiFieldLabel("created")} value={String(runSummary.created)} />
                <SummaryField label="Дедуплицировано" value={String(runSummary.deduped)} />
                <SummaryField label={uiFieldLabel("errors")} value={String(runSummary.errors)} />
                <SummaryField label="Элементов журнала" value={String(runSummary.item_count)} />
              </div>
              </div>
            )}
          </section>

          <section
            className="rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
            data-testid="regular-task-run-task-list"
          >
            <div className="mb-3">
              <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">Задачи по запуску</h2>
              <p className="mt-0.5 text-xs text-zinc-600 dark:text-zinc-400">
                Созданные, найденные по дедупликации и проблемные задачи
              </p>
            </div>

            {taskListState.kind === "select_run" ? (
              <div className="rounded-lg border border-dashed border-zinc-300 p-4 text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
                Выберите запуск слева.
              </div>
            ) : null}

            {taskListState.kind === "loading" ? (
              <div className="text-sm text-zinc-600 dark:text-zinc-400">Загрузка списка задач…</div>
            ) : null}

            {taskListState.kind === "unavailable" ? (
              <div
                className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100"
                data-testid="regular-task-run-task-list-unavailable"
              >
                Список задач недоступен: элементы журнала отсутствуют.
              </div>
            ) : null}

            {taskListState.kind === "expected_not_loaded" ? (
              <div
                className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100"
                data-testid="regular-task-run-task-list-expected-not-loaded"
              >
                {RUN_TASK_LIST_EXPECTED_NOT_LOADED_MESSAGE}
              </div>
            ) : null}

            {taskListState.kind === "none_expected" ? (
              <div
                className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-400"
                data-testid="regular-task-run-task-list-empty"
              >
                По этому запуску задачи не создавались.
              </div>
            ) : null}

            {taskListState.kind === "rows" ? (
              <div
                className="overflow-auto rounded-xl border border-zinc-200 dark:border-zinc-800"
                data-testid="regular-task-run-task-list-table-wrap"
              >
                <table className="min-w-full text-sm" data-testid="regular-task-run-task-list-table">
                  <thead className="bg-zinc-100 text-left dark:bg-zinc-900">
                    <tr>
                      <th className="min-w-[180px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Задача</th>
                      <th className="min-w-[140px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">
                        Исполнитель
                      </th>
                      <th className="w-[110px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Дедлайн</th>
                      <th className="w-[130px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Результат</th>
                      <th className="w-[88px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Открыть</th>
                    </tr>
                  </thead>
                  <tbody>
                    {taskListState.rows.map((row) => (
                      <tr
                        key={row.item_id}
                        data-testid={`regular-task-run-task-row-${row.item_id}`}
                        className="border-t border-zinc-200 dark:border-zinc-800"
                      >
                        <td className="px-3 py-2 font-medium text-zinc-900 dark:text-zinc-50">{row.task_title}</td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{row.executor_label}</td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{row.deadline_label}</td>
                        <td className={`px-3 py-2 text-xs font-medium ${runTaskOutcomeTone(row.outcome)}`}>
                          {row.outcome_label}
                        </td>
                        <td className="px-3 py-2 text-xs">
                          {row.task_href ? (
                            <Link
                              href={row.task_href}
                              className="font-medium text-blue-700 hover:underline dark:text-blue-300"
                              data-testid={`regular-task-run-task-open-${row.item_id}`}
                            >
                              Открыть
                            </Link>
                          ) : (
                            <span
                              className="text-zinc-500 dark:text-zinc-400"
                              data-testid={`regular-task-run-task-open-unavailable-${row.item_id}`}
                            >
                              —
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>

          <section
            className="rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900"
            data-testid="regular-task-run-items-section"
          >
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
                  Элементы запуска
                  {selectedRun ? ` · ${runTitleLabel(selectedRun.run_id)}` : ""}
                </h2>
                <p className="mt-0.5 text-xs text-zinc-600 dark:text-zinc-400">
                  Показано: {filteredItems.length} из {items.length}
                </p>
              </div>

              <button
                type="button"
                onClick={onRefreshItems}
                disabled={!selectedRunId || itemsLoading}
                className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-xs text-zinc-800 hover:bg-zinc-100 disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200"
              >
                {itemsLoading ? "Обновление…" : "Обновить"}
              </button>
            </div>

            {!selectedRunId ? (
              <div className="rounded-lg border border-dashed border-zinc-300 p-4 text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-400">
                Выберите запуск слева.
              </div>
            ) : (
              <>
                <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-[auto_minmax(0,1fr)]">
                  <label className="flex items-center gap-2 text-sm text-zinc-800 dark:text-zinc-200">
                    <input
                      type="checkbox"
                      checked={onlyIssues}
                      onChange={(e) => onOnlyIssuesChange(e.target.checked)}
                      className="h-4 w-4"
                      data-testid="regular-task-runs-only-issues"
                    />
                    Только ошибки
                  </label>

                  <input
                    value={search}
                    onChange={(e) => onSearchChange(e.target.value)}
                    className="w-full rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-900 outline-none dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50"
                    placeholder="Фильтр по шаблону, роли, периоду, ошибке…"
                  />
                </div>

                {itemsError ? <div className="mb-3 text-sm text-red-700 dark:text-red-300">{itemsError}</div> : null}
                {itemsLoading ? <div className="mb-3 text-sm text-zinc-600 dark:text-zinc-400">Загрузка…</div> : null}

                {!itemsLoading && itemsEmptyMessage ? (
                  <div
                    className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm text-zinc-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-400"
                    data-testid="regular-task-run-items-empty"
                  >
                    {itemsEmptyMessage}
                  </div>
                ) : null}

                {!itemsLoading && filteredItems.length > 0 ? (
                  <div
                    className="max-h-[min(70vh,720px)] overflow-auto rounded-xl border border-zinc-200 dark:border-zinc-800"
                    data-testid="regular-task-run-items-scroll"
                  >
                    <table className="min-w-full text-sm" data-testid="regular-task-run-items-table">
                      <thead className="sticky top-0 z-10 bg-zinc-100 text-left dark:bg-zinc-900">
                        <tr>
                          <th className="w-12 px-2 py-2 font-medium text-zinc-700 dark:text-zinc-300">№</th>
                          <th className="min-w-[180px] px-2 py-2 font-medium text-zinc-700 dark:text-zinc-300">
                            Шаблон / задача
                          </th>
                          <th className="w-[100px] px-2 py-2 font-medium text-zinc-700 dark:text-zinc-300">
                            Тип результата
                          </th>
                          <th className="w-[80px] px-2 py-2 font-medium text-zinc-700 dark:text-zinc-300">Задача ID</th>
                          <th className="w-[110px] px-2 py-2 font-medium text-zinc-700 dark:text-zinc-300">
                            {uiFieldLabel("period")}
                          </th>
                          <th className="min-w-[140px] px-2 py-2 font-medium text-zinc-700 dark:text-zinc-300">
                            Роль исполнителя
                          </th>
                          <th className="w-[70px] px-2 py-2 font-medium text-zinc-700 dark:text-zinc-300">
                            {uiFieldLabel("due")}
                          </th>
                          <th className="min-w-[120px] px-2 py-2 font-medium text-zinc-700 dark:text-zinc-300">Ошибка</th>
                          <th className="min-w-[160px] px-2 py-2 font-medium text-zinc-700 dark:text-zinc-300">
                            Происхождение
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredItems.map((it, index) => {
                          const err = String(it.error ?? "").trim();
                          return (
                            <tr
                              key={it.item_id}
                              data-testid={`regular-task-run-item-${it.item_id}`}
                              className="border-t border-zinc-200 align-top dark:border-zinc-800"
                            >
                              <td className="px-2 py-2 text-zinc-600 dark:text-zinc-400">{index + 1}</td>
                              <td className="px-2 py-2">
                                <div className="font-medium text-zinc-900 dark:text-zinc-50">{itemTitleLabel(it)}</div>
                                <div className="text-[11px] text-zinc-500">шаблон #{it.regular_task_id}</div>
                              </td>
                              <td className={`px-2 py-2 text-xs font-medium ${itemOutcomeTone(it)}`}>
                                {itemOutcomeLabel(it)}
                              </td>
                              <td className="px-2 py-2 text-zinc-700 dark:text-zinc-300">
                                {it.meta?.task_id ?? "—"}
                              </td>
                              <td className="px-2 py-2 text-zinc-700 dark:text-zinc-300">{periodLabel(it)}</td>
                              <td className="px-2 py-2 text-zinc-700 dark:text-zinc-300">{roleLabel(it)}</td>
                              <td className="px-2 py-2 text-zinc-700 dark:text-zinc-300">{yesNo(it.is_due)}</td>
                              <td className="px-2 py-2 text-xs text-red-700 dark:text-red-300">
                                {err ? translateRunIssueMessage(err) : "—"}
                              </td>
                              <td className="px-2 py-2">
                                <OriginCompact item={it} />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : null}

                {selectedRun ? (
                  <details
                    className="mt-3 rounded-xl border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-950"
                    data-testid="regular-task-run-json-details"
                  >
                    <summary className="cursor-pointer text-sm text-zinc-700 dark:text-zinc-300">
                      Технические детали (JSON)
                    </summary>
                    <pre className="mt-2 max-h-80 overflow-auto text-xs text-zinc-800 dark:text-zinc-200">
                      {JSON.stringify({ run: selectedRun, items }, null, 2)}
                    </pre>
                  </details>
                ) : null}
              </>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
