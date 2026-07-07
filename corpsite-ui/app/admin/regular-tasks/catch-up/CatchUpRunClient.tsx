"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import React from "react";

import CatchUpReviewPanel from "./CatchUpReviewPanel";

import SchedulerStatusPanel from "@/app/regular-tasks/_components/SchedulerStatusPanel";
import RegularTaskTemplateFiltersBar from "@/components/RegularTaskTemplateFiltersBar";
import {
  apiCatchUpRegularTasks,
  apiFetchJson,
  apiGetRegularTaskRunItems,
  type CatchUpRegularTasksParams,
  type CatchUpRegularTasksResult,
} from "@/lib/api";
import {
  buildCatchUpPeriodOptions,
  findCatchUpPeriodOption,
  resolveDefaultPeriodKey,
  type CatchUpPeriodOption,
} from "@/lib/catchUpPeriodOptions";
import {
  buildCatchUpPayload,
  payloadsEquivalent,
  resolveSuggestedScheduleTypeForPeriod,
  validateCatchUpForm,
  type CatchUpFormState,
  type CatchUpScheduleType,
} from "@/lib/catchUpWorkflow";
import {
  catchUpUiLabel,
  formatThrownError,
  scheduleTypeLabel,
} from "@/lib/i18n";
import {
  buildRegularTasksListApiQuery,
  clearExecutorRoleIfNotAllowed,
  deriveExecutorRoleOptionsFromTemplates,
  EMPTY_REGULAR_TASK_TEMPLATE_LIST_FILTERS,
  stripLegacyOrgScopeParams,
  stripExecutorRoleFilter,
  type RegularTaskTemplateListFilters,
  type TemplateExecutorRoleSource,
} from "@/lib/regularTaskTemplateListFilters";
import { type RegularTaskRunItemRow } from "@/lib/regularTaskRunJournal";

type TemplateRow = TemplateExecutorRoleSource & {
  regular_task_id: number;
  title: string;
  is_active?: boolean;
  archived_at?: string | null;
};

type TemplatesResponse = {
  items?: TemplateRow[];
};

const SCHEDULE_TYPE_OPTIONS: Array<{ value: CatchUpScheduleType; label: string }> = [
  { value: "weekly", label: scheduleTypeLabel("weekly") },
  { value: "monthly", label: scheduleTypeLabel("monthly") },
  { value: "yearly", label: scheduleTypeLabel("yearly") },
];

const WORKFLOW_STEPS = [
  { id: 1, labelKey: "workflow_dry_run" },
  { id: 2, labelKey: "workflow_review" },
  { id: 3, labelKey: "workflow_confirm" },
  { id: 4, labelKey: "workflow_execute" },
  { id: 5, labelKey: "workflow_journal" },
] as const;

function normalizeTemplateRows(data: TemplatesResponse | TemplateRow[]): TemplateRow[] {
  const rows = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];

  return rows
    .map((t) => ({
      regular_task_id: Number(t.regular_task_id),
      title: String(t.title ?? "").trim() || `Шаблон #${t.regular_task_id}`,
      is_active: t.is_active,
      archived_at: t.archived_at ?? null,
      executor_role_id: t.executor_role_id ?? null,
      executor_role_name: t.executor_role_name ?? null,
      executor_role_code: t.executor_role_code ?? null,
    }))
    .filter(
      (t) =>
        Number.isFinite(t.regular_task_id) &&
        t.regular_task_id > 0 &&
        t.is_active !== false &&
        !t.archived_at,
    );
}

function resolveActiveStep(params: {
  previewResult: CatchUpRegularTasksResult | null;
  previewItems: RegularTaskRunItemRow[];
  reviewConfirmed: boolean;
  liveResult: CatchUpRegularTasksResult | null;
}): number {
  if (params.liveResult) return 5;
  if (params.previewResult && params.reviewConfirmed) return 4;
  if (params.previewResult && params.previewItems.length >= 0) return 2;
  return 1;
}

const NAV_BUTTON_CLASS =
  "rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-4 py-2 text-sm font-medium text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700";

function CatchUpNavActions({ dryRunId }: { dryRunId?: number | null }) {
  return (
    <div className="flex flex-wrap gap-2" data-testid="catch-up-nav-actions">
      <Link href="/admin/regular-tasks" className={NAV_BUTTON_CLASS} data-testid="catch-up-nav-templates">
        {catchUpUiLabel("nav_to_templates")}
      </Link>
      <Link href="/regular-task-runs" className={NAV_BUTTON_CLASS} data-testid="catch-up-nav-journal">
        {catchUpUiLabel("nav_to_journal")}
      </Link>
      {dryRunId ? (
        <Link
          href={`/regular-task-runs?run_id=${dryRunId}`}
          className="rounded-xl border border-blue-200 dark:border-blue-900/50 bg-blue-50 dark:bg-blue-950/30 px-4 py-2 text-sm font-medium text-blue-700 dark:text-blue-300 transition hover:bg-blue-100 dark:hover:bg-blue-950/50"
          data-testid="catch-up-nav-dry-run-journal"
        >
          {catchUpUiLabel("dry_run_journal_link")} #{dryRunId}
        </Link>
      ) : null}
    </div>
  );
}

function WorkflowStepper({ activeStep }: { activeStep: number }) {
  return (
    <ol className="flex flex-wrap gap-2" data-testid="catch-up-workflow-steps">
      {WORKFLOW_STEPS.map((step) => {
        const done = activeStep > step.id;
        const current = activeStep === step.id;
        return (
          <li
            key={step.id}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              current
                ? "bg-blue-600 text-white"
                : done
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200"
                  : "bg-zinc-200 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
            }`}
          >
            {step.id}. {catchUpUiLabel(step.labelKey)}
          </li>
        );
      })}
    </ol>
  );
}

export default function CatchUpRunClient() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const [scheduleType, setScheduleType] = React.useState<CatchUpScheduleType>("weekly");
  const [scheduleTypeManuallySet, setScheduleTypeManuallySet] = React.useState(false);
  const [periodKey, setPeriodKey] = React.useState(() => resolveDefaultPeriodKey("weekly"));
  const [listFilters, setListFilters] = React.useState<RegularTaskTemplateListFilters>(
    EMPTY_REGULAR_TASK_TEMPLATE_LIST_FILTERS,
  );
  const [regularTaskId, setRegularTaskId] = React.useState("");
  const [scopeRoleSourceTemplates, setScopeRoleSourceTemplates] = React.useState<TemplateRow[]>([]);
  const [scopeRolesLoading, setScopeRolesLoading] = React.useState(false);
  const [templateOptions, setTemplateOptions] = React.useState<TemplateRow[]>([]);
  const [templatesLoading, setTemplatesLoading] = React.useState(false);

  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const [previewResult, setPreviewResult] = React.useState<CatchUpRegularTasksResult | null>(null);
  const [previewItems, setPreviewItems] = React.useState<RegularTaskRunItemRow[]>([]);
  const [previewItemsError, setPreviewItemsError] = React.useState<string | null>(null);
  const [lockedPayload, setLockedPayload] = React.useState<CatchUpRegularTasksParams | null>(null);
  const [reviewConfirmed, setReviewConfirmed] = React.useState(false);
  const [liveResult, setLiveResult] = React.useState<CatchUpRegularTasksResult | null>(null);
  const [liveItems, setLiveItems] = React.useState<RegularTaskRunItemRow[]>([]);

  const parsedRegularTaskId = React.useMemo(() => {
    const s = regularTaskId.trim();
    if (!s) return null;
    const n = Number(s);
    return Number.isFinite(n) && n > 0 ? Math.trunc(n) : null;
  }, [regularTaskId]);

  const scopeListFilters = React.useMemo(
    () => stripExecutorRoleFilter(listFilters),
    [listFilters],
  );

  const filterExecutorRoleOptions = React.useMemo(
    () => deriveExecutorRoleOptionsFromTemplates(scopeRoleSourceTemplates),
    [scopeRoleSourceTemplates],
  );

  const periodOptions = React.useMemo(
    () => buildCatchUpPeriodOptions(scheduleType),
    [scheduleType],
  );

  const selectedPeriod = React.useMemo<CatchUpPeriodOption | null>(
    () => findCatchUpPeriodOption(scheduleType, periodKey),
    [scheduleType, periodKey],
  );

  const formState = React.useMemo<CatchUpFormState>(
    () => ({
      preset: selectedPeriod?.preset ?? "past_week",
      manualDate: selectedPeriod?.manualDate ?? "",
      scheduleType,
      orgGroupId: listFilters.org_group_id ?? null,
      orgUnitId: listFilters.org_unit_id ?? null,
      executorRoleId: listFilters.executor_role_id ?? null,
      regularTaskId: parsedRegularTaskId,
    }),
    [selectedPeriod, scheduleType, listFilters, parsedRegularTaskId],
  );

  const activeStep = resolveActiveStep({
    previewResult,
    previewItems,
    reviewConfirmed,
    liveResult,
  });

  const payloadDrift =
    lockedPayload != null &&
    previewResult != null &&
    !payloadsEquivalent(lockedPayload, buildCatchUpPayload(formState, true));

  const templatesDue = previewResult?.stats?.templates_due ?? 0;
  const hasTemplatesToRun = templatesDue > 0;

  React.useEffect(() => {
    if (!periodOptions.some((opt) => opt.key === periodKey)) {
      setPeriodKey(periodOptions[0]?.key ?? "");
    }
  }, [periodOptions, periodKey]);

  React.useEffect(() => {
    const params = new URLSearchParams(sp.toString());
    if (!stripLegacyOrgScopeParams(params)) return;
    const next = params.toString();
    router.replace(next ? `${pathname}?${next}` : pathname);
  }, [pathname, router, sp]);

  const resetWorkflow = React.useCallback(() => {
    setPreviewResult(null);
    setPreviewItems([]);
    setPreviewItemsError(null);
    setLockedPayload(null);
    setReviewConfirmed(false);
    setLiveResult(null);
    setLiveItems([]);
  }, []);

  React.useEffect(() => {
    setListFilters((prev) => clearExecutorRoleIfNotAllowed(prev, filterExecutorRoleOptions));
  }, [filterExecutorRoleOptions]);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setScopeRolesLoading(true);
      try {
        const data = await apiFetchJson<TemplatesResponse>("/regular-tasks", {
          query: buildRegularTasksListApiQuery(scopeListFilters, {
            status: "active",
            limit: 200,
            offset: 0,
          }),
        });
        if (!cancelled) setScopeRoleSourceTemplates(normalizeTemplateRows(data));
      } catch {
        if (!cancelled) setScopeRoleSourceTemplates([]);
      } finally {
        if (!cancelled) setScopeRolesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [scopeListFilters]);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setTemplatesLoading(true);
      try {
        const data = await apiFetchJson<TemplatesResponse>("/regular-tasks", {
          query: {
            ...buildRegularTasksListApiQuery(listFilters, {
              status: "active",
              limit: 200,
              offset: 0,
            }),
            schedule_type: scheduleType,
          },
        });
        if (!cancelled) setTemplateOptions(normalizeTemplateRows(data));
      } catch {
        if (!cancelled) setTemplateOptions([]);
      } finally {
        if (!cancelled) setTemplatesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [scheduleType, listFilters]);

  React.useEffect(() => {
    if (!regularTaskId.trim()) return;
    const selectedId = Number(regularTaskId);
    if (!Number.isFinite(selectedId) || selectedId <= 0) return;
    if (!templateOptions.some((t) => t.regular_task_id === selectedId)) {
      setRegularTaskId("");
    }
  }, [templateOptions, regularTaskId]);

  function handleListFiltersChange(next: RegularTaskTemplateListFilters) {
    setListFilters(next);
    resetWorkflow();
  }

  function handleScheduleTypeChange(next: CatchUpScheduleType) {
    setScheduleTypeManuallySet(true);
    setScheduleType(next);
    setPeriodKey(resolveDefaultPeriodKey(next));
    resetWorkflow();
  }

  function handlePeriodChange(nextKey: string) {
    const option = findCatchUpPeriodOption(scheduleType, nextKey);
    if (!option) return;

    if (!scheduleTypeManuallySet) {
      const suggested = resolveSuggestedScheduleTypeForPeriod(option);
      if (suggested != null && suggested !== scheduleType) {
        setScheduleType(suggested);
        setPeriodKey(resolveDefaultPeriodKey(suggested));
        resetWorkflow();
        return;
      }
    }

    setPeriodKey(nextKey);
    resetWorkflow();
  }

  async function loadRunItems(runId: number): Promise<RegularTaskRunItemRow[]> {
    const { items } = await apiGetRegularTaskRunItems({ run_id: runId });
    return items as RegularTaskRunItemRow[];
  }

  async function handlePreview() {
    const validation = validateCatchUpForm(formState);
    if (validation) {
      setSubmitError(validation);
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    resetWorkflow();

    const payload = buildCatchUpPayload(formState, true);

    try {
      const result = await apiCatchUpRegularTasks(payload);
      setPreviewResult(result);
      setLockedPayload(payload);

      try {
        const items = await loadRunItems(result.run_id);
        setPreviewItems(items);
      } catch (err) {
        setPreviewItemsError(
          formatThrownError(err, { fallback: "Пробный прогон выполнен, но items не загрузились." }),
        );
      }
    } catch (err) {
      setSubmitError(formatThrownError(err, { fallback: "Не удалось выполнить пробный прогон." }));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLiveRun() {
    if (!lockedPayload || !previewResult) {
      setSubmitError("Сначала выполните пробный прогон.");
      return;
    }
    if (!reviewConfirmed) {
      setSubmitError("Подтвердите проверку результата пробного прогона.");
      return;
    }
    if (payloadDrift) {
      setSubmitError("Параметры формы изменились после пробного прогона. Выполните пробный прогон заново.");
      return;
    }
    if (!hasTemplatesToRun) {
      setSubmitError(catchUpUiLabel("zero_templates_warning"));
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      const result = await apiCatchUpRegularTasks({ ...lockedPayload, dry_run: false });
      setLiveResult(result);

      try {
        const items = await loadRunItems(result.run_id);
        setLiveItems(items);
      } catch {
        setLiveItems([]);
      }
    } catch (err) {
      setSubmitError(formatThrownError(err, { fallback: "Не удалось выполнить боевой прогон." }));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 p-4 md:p-6">
      <div className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Догоняющий запуск
        </h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Безопасный сценарий: {catchUpUiLabel("workflow_dry_run").toLowerCase()} →{" "}
          {catchUpUiLabel("workflow_review").toLowerCase()} →{" "}
          {catchUpUiLabel("workflow_confirm").toLowerCase()} →{" "}
          {catchUpUiLabel("workflow_execute").toLowerCase()} →{" "}
          {catchUpUiLabel("workflow_journal").toLowerCase()}. SSH и curl не требуются.
        </p>
        <WorkflowStepper activeStep={activeStep} />
        <CatchUpNavActions dryRunId={previewResult?.run_id} />
      </div>

      <SchedulerStatusPanel variant="compact" />

      <section className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-4 shadow-sm">
        <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">1. Параметры и пробный прогон</h2>

        <RegularTaskTemplateFiltersBar
          className="mt-4"
          filters={listFilters}
          onChange={handleListFiltersChange}
          executorRoleOptions={filterExecutorRoleOptions}
          executorRolesLoading={scopeRolesLoading}
        />

        <div className="mt-4 grid gap-4 md:grid-cols-2" data-testid="catch-up-form-grid">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-zinc-800 dark:text-zinc-200">{catchUpUiLabel("schedule_type")}</span>
            <select
              className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
              value={scheduleType}
              onChange={(e) => handleScheduleTypeChange(e.target.value as CatchUpScheduleType)}
              data-testid="catch-up-schedule-type"
            >
              {SCHEDULE_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-zinc-800 dark:text-zinc-200">{catchUpUiLabel("preset")}</span>
            <select
              className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
              value={periodKey}
              onChange={(e) => handlePeriodChange(e.target.value)}
              data-testid="catch-up-period-select"
            >
              {periodOptions.map((opt) => (
                <option key={opt.key} value={opt.key}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm md:col-span-2">
            <span className="font-medium text-zinc-800 dark:text-zinc-200">
              {catchUpUiLabel("regular_task_id")} (опционально)
            </span>
            <select
              className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
              value={regularTaskId}
              onChange={(e) => {
                setRegularTaskId(e.target.value);
                resetWorkflow();
              }}
              disabled={templatesLoading}
              data-testid="catch-up-template-select"
            >
              <option value="">Все шаблоны</option>
              {templateOptions.map((template) => (
                <option key={template.regular_task_id} value={String(template.regular_task_id)}>
                  {`${template.title} (#${template.regular_task_id})`}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-4">
          <button
            type="button"
            disabled={submitting}
            onClick={handlePreview}
            className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-4 py-2 text-sm font-medium text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
            data-testid="catch-up-dry-run"
          >
            {submitting ? "Выполняется..." : catchUpUiLabel("workflow_dry_run")}
          </button>
        </div>

        {submitError ? (
          <div className="mt-3 rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 p-3 text-sm text-red-700 dark:text-red-300">
            {submitError}
          </div>
        ) : null}

        {payloadDrift ? (
          <div className="mt-3 rounded-xl border border-amber-200 dark:border-amber-900/55 bg-amber-50 dark:bg-amber-950/35 p-3 text-sm text-amber-800 dark:text-amber-200">
            Параметры формы изменились после пробного прогона. Повторите пробный прогон перед боевым запуском.
          </div>
        ) : null}
      </section>

      {previewResult ? (
        <>
          <CatchUpReviewPanel
            title={`2. ${catchUpUiLabel("workflow_review")}`}
            result={previewResult}
            items={previewItems}
            isDryRunPreview
            showJournalLink
          />
          {previewItemsError ? (
            <div className="rounded-xl border border-amber-200 dark:border-amber-900/55 bg-amber-50 dark:bg-amber-950/35 p-3 text-sm text-amber-800 dark:text-amber-200">
              {previewItemsError}
            </div>
          ) : null}

          <section
            className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-4 shadow-sm"
            data-testid="catch-up-confirm-section"
          >
            <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">
              3. {catchUpUiLabel("workflow_confirm")} перед боевым запуском
            </h2>
            <p className="mt-2 text-sm text-amber-800 dark:text-amber-200">
              Рекомендуется выполнить резервную копию БД перед боевым запуском (на VPS:{" "}
              <code className="rounded bg-amber-100/80 px-1 dark:bg-amber-950/50">scripts/backup_db.sh</code>
              ).
            </p>
            {!hasTemplatesToRun ? (
              <div
                className="mt-4 rounded-xl border border-amber-200 dark:border-amber-900/55 bg-amber-50 dark:bg-amber-950/35 p-3 text-sm text-amber-800 dark:text-amber-200"
                data-testid="catch-up-zero-templates-warning"
              >
                {catchUpUiLabel("zero_templates_warning")}{" "}
                <Link
                  href="/admin/regular-tasks"
                  className="font-medium text-blue-700 underline dark:text-blue-300"
                >
                  {catchUpUiLabel("nav_to_templates")}
                </Link>
              </div>
            ) : null}
            <label className="mt-4 flex items-start gap-2 text-sm text-zinc-800 dark:text-zinc-200">
              <input
                type="checkbox"
                className="mt-1"
                checked={reviewConfirmed}
                onChange={(e) => setReviewConfirmed(e.target.checked)}
                data-testid="catch-up-review-confirmed"
              />
              <span>
                Я проверил результат пробного прогона (период, шаблоны, {catchUpUiLabel("due_date").toLowerCase()}
                ).
              </span>
            </label>

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <button
                type="button"
                disabled={submitting || !reviewConfirmed || payloadDrift || !hasTemplatesToRun}
                onClick={handleLiveRun}
                className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                data-testid="catch-up-execute"
              >
                {submitting ? "Выполняется..." : catchUpUiLabel("workflow_execute")}
              </button>
              {!liveResult ? (
                <Link
                  href="/regular-task-runs"
                  className="text-sm font-medium text-zinc-600 underline transition hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
                  data-testid="catch-up-exit-without-live"
                >
                  {catchUpUiLabel("exit_without_live")}
                </Link>
              ) : null}
            </div>
          </section>
        </>
      ) : null}

      {liveResult ? (
        <CatchUpReviewPanel
          title={`4–5. ${catchUpUiLabel("workflow_execute")} и ${catchUpUiLabel("workflow_journal")}`}
          result={liveResult}
          items={liveItems}
          isDryRunPreview={false}
          showJournalLink
        />
      ) : null}
    </div>
  );
}
