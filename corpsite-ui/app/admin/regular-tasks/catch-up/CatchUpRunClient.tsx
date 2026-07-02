"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import React from "react";

import CatchUpReviewPanel from "./CatchUpReviewPanel";

import SchedulerStatusPanel from "@/app/regular-tasks/_components/SchedulerStatusPanel";
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
  validateCatchUpForm,
  type CatchUpFormState,
  type CatchUpScheduleType,
} from "@/lib/catchUpWorkflow";
import {
  buildOrgUnitSelectGroups,
  loadOrgUnitSelectOptions,
  type OrgUnitSelectOption,
} from "@/lib/orgUnitsSelect";
import {
  catchUpUiLabel,
  formatThrownError,
  scheduleTypeLabel,
  uiFieldLabel,
} from "@/lib/i18n";
import { directoryRoleLabel, type RegularTaskRunItemRow } from "@/lib/regularTaskRunJournal";

type OrgGroupFilter = "all" | string;

type DeptGroupRow = {
  group_id: number;
  group_name: string;
  effective_log_group?: string | null;
};

type DeptGroupsResponse = {
  items?: Array<{
    group_id: number;
    group_name?: string;
    effective_log_group?: string | null;
  }>;
};

type RoleRow = {
  role_id: number;
  role_name?: string | null;
  name?: string | null;
  role_code?: string | null;
  code?: string | null;
};

type RolesResponse = {
  items?: RoleRow[];
};

type TemplateRow = {
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

function readEnvGroupId(name: string, fallback: number): number {
  const raw = String(process.env[name] ?? "").trim();
  if (!raw) return fallback;
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  return n;
}

const ENV_ORG_GROUP_IDS: Record<string, number> = {
  clinical: readEnvGroupId("NEXT_PUBLIC_ORG_GROUP_ID_CLINICAL", 1),
  paraclinical: readEnvGroupId("NEXT_PUBLIC_ORG_GROUP_ID_PARACLINICAL", 2),
  admin_household: readEnvGroupId("NEXT_PUBLIC_ORG_GROUP_ID_ADMIN", 3),
};

function resolveOrgGroupId(filter: OrgGroupFilter, deptGroups: DeptGroupRow[]): number | null {
  if (filter === "all") return null;

  const bySlug = deptGroups.find((g) => g.effective_log_group === filter);
  if (bySlug) return bySlug.group_id;

  const envId = ENV_ORG_GROUP_IDS[filter];
  if (envId != null && deptGroups.some((g) => g.group_id === envId)) return envId;

  return envId ?? null;
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
  const sp = useSearchParams();
  const orgUnitFromUrl = sp.get("org_unit_id") ?? "";

  const [scheduleType, setScheduleType] = React.useState<CatchUpScheduleType>("weekly");
  const [periodKey, setPeriodKey] = React.useState(() => resolveDefaultPeriodKey("weekly"));
  const [orgGroup, setOrgGroup] = React.useState<OrgGroupFilter>("all");
  const [deptGroups, setDeptGroups] = React.useState<DeptGroupRow[]>([]);
  const [orgUnitId, setOrgUnitId] = React.useState(orgUnitFromUrl);
  const [executorRoleId, setExecutorRoleId] = React.useState("");
  const [regularTaskId, setRegularTaskId] = React.useState("");
  const [roleOptions, setRoleOptions] = React.useState<RoleRow[]>([]);
  const [rolesLoading, setRolesLoading] = React.useState(false);
  const [templateOptions, setTemplateOptions] = React.useState<TemplateRow[]>([]);
  const [templatesLoading, setTemplatesLoading] = React.useState(false);
  const [ownerUnitOptions, setOwnerUnitOptions] = React.useState<OrgUnitSelectOption[]>([]);
  const [ownerUnitLoading, setOwnerUnitLoading] = React.useState(false);
  const [ownerUnitLoadError, setOwnerUnitLoadError] = React.useState<string | null>(null);

  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const [previewResult, setPreviewResult] = React.useState<CatchUpRegularTasksResult | null>(null);
  const [previewItems, setPreviewItems] = React.useState<RegularTaskRunItemRow[]>([]);
  const [previewItemsError, setPreviewItemsError] = React.useState<string | null>(null);
  const [lockedPayload, setLockedPayload] = React.useState<CatchUpRegularTasksParams | null>(null);
  const [reviewConfirmed, setReviewConfirmed] = React.useState(false);
  const [liveResult, setLiveResult] = React.useState<CatchUpRegularTasksResult | null>(null);
  const [liveItems, setLiveItems] = React.useState<RegularTaskRunItemRow[]>([]);

  const selectedOrgGroupId = React.useMemo(
    () => resolveOrgGroupId(orgGroup, deptGroups),
    [orgGroup, deptGroups],
  );

  const parsedOrgUnitId = React.useMemo(() => {
    const s = (orgUnitId || orgUnitFromUrl).trim();
    if (!s) return null;
    const n = Number(s);
    return Number.isFinite(n) && n > 0 ? Math.trunc(n) : null;
  }, [orgUnitId, orgUnitFromUrl]);

  const parsedExecutorRoleId = React.useMemo(() => {
    const s = executorRoleId.trim();
    if (!s) return null;
    const n = Number(s);
    return Number.isFinite(n) && n > 0 ? Math.trunc(n) : null;
  }, [executorRoleId]);

  const parsedRegularTaskId = React.useMemo(() => {
    const s = regularTaskId.trim();
    if (!s) return null;
    const n = Number(s);
    return Number.isFinite(n) && n > 0 ? Math.trunc(n) : null;
  }, [regularTaskId]);

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
      orgGroupId: selectedOrgGroupId,
      orgUnitId: parsedOrgUnitId,
      executorRoleId: parsedExecutorRoleId,
      regularTaskId: parsedRegularTaskId,
    }),
    [
      selectedPeriod,
      scheduleType,
      selectedOrgGroupId,
      parsedOrgUnitId,
      parsedExecutorRoleId,
      parsedRegularTaskId,
    ],
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
    setOrgUnitId(orgUnitFromUrl);
  }, [orgUnitFromUrl]);

  const resetWorkflow = React.useCallback(() => {
    setPreviewResult(null);
    setPreviewItems([]);
    setPreviewItemsError(null);
    setLockedPayload(null);
    setReviewConfirmed(false);
    setLiveResult(null);
    setLiveItems([]);
  }, []);

  const orgGroupOptions = React.useMemo(() => {
    const opts: Array<{ value: OrgGroupFilter; label: string }> = [
      { value: "all", label: "Все группы отделений" },
    ];
    for (const g of deptGroups) {
      const slug = g.effective_log_group || String(g.group_id);
      opts.push({ value: slug, label: g.group_name });
    }
    return opts;
  }, [deptGroups]);

  const groupLabelById = React.useMemo(() => {
    return new Map(deptGroups.map((g) => [g.group_id, g.group_name]));
  }, [deptGroups]);

  const filteredOwnerUnitOptions = React.useMemo(() => {
    if (selectedOrgGroupId == null) return ownerUnitOptions;
    return ownerUnitOptions.filter((u) => Number(u.group_id) === Number(selectedOrgGroupId));
  }, [ownerUnitOptions, selectedOrgGroupId]);

  const unitSelectGroups = React.useMemo(
    () => buildOrgUnitSelectGroups(filteredOwnerUnitOptions, groupLabelById),
    [filteredOwnerUnitOptions, groupLabelById],
  );

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await apiFetchJson<DeptGroupsResponse>("/directory/department-groups", {
          query: { status: "active", limit: 200 },
        });
        const rows = Array.isArray(data?.items) ? data.items : [];
        if (!cancelled) {
          setDeptGroups(
            rows
              .map((g) => ({
                group_id: Number(g.group_id),
                group_name: String(g.group_name ?? "").trim() || `#${g.group_id}`,
                effective_log_group: g.effective_log_group ?? null,
              }))
              .filter((g) => Number.isFinite(g.group_id) && g.group_id > 0),
          );
        }
      } catch {
        if (!cancelled) setDeptGroups([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setOwnerUnitLoading(true);
      setOwnerUnitLoadError(null);
      try {
        const options = await loadOrgUnitSelectOptions();
        if (!cancelled) setOwnerUnitOptions(options);
      } catch (err) {
        if (!cancelled) {
          setOwnerUnitOptions([]);
          setOwnerUnitLoadError(formatThrownError(err, { fallback: "Не удалось загрузить список отделений." }));
        }
      } finally {
        if (!cancelled) setOwnerUnitLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setRolesLoading(true);
      try {
        const data = await apiFetchJson<RolesResponse>("/directory/roles", {
          query: { is_active: true, limit: 200 },
        });
        const rows = Array.isArray(data?.items) ? data.items : [];
        if (!cancelled) {
          setRoleOptions(
            rows
              .map((r) => ({
                role_id: Number(r.role_id),
                role_name: r.role_name ?? r.name ?? null,
                name: r.name ?? r.role_name ?? null,
                role_code: r.role_code ?? r.code ?? null,
                code: r.code ?? r.role_code ?? null,
              }))
              .filter((r) => Number.isFinite(r.role_id) && r.role_id > 0),
          );
        }
      } catch {
        if (!cancelled) setRoleOptions([]);
      } finally {
        if (!cancelled) setRolesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setTemplatesLoading(true);
      try {
        const data = await apiFetchJson<TemplatesResponse>("/regular-tasks", {
          query: {
            status: "active",
            schedule_type: scheduleType,
            executor_role_id: parsedExecutorRoleId ?? undefined,
            org_group_id: selectedOrgGroupId ?? undefined,
            org_unit_id: parsedOrgUnitId ?? undefined,
            limit: 200,
          },
        });
        const rows = Array.isArray(data?.items) ? data.items : [];
        if (!cancelled) {
          setTemplateOptions(
            rows
              .map((t) => ({
                regular_task_id: Number(t.regular_task_id),
                title: String(t.title ?? "").trim() || `Шаблон #${t.regular_task_id}`,
                is_active: t.is_active,
                archived_at: t.archived_at ?? null,
              }))
              .filter(
                (t) =>
                  Number.isFinite(t.regular_task_id) &&
                  t.regular_task_id > 0 &&
                  t.is_active !== false &&
                  !t.archived_at,
              ),
          );
        }
      } catch {
        if (!cancelled) setTemplateOptions([]);
      } finally {
        if (!cancelled) setTemplatesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [scheduleType, selectedOrgGroupId, parsedOrgUnitId, parsedExecutorRoleId]);

  React.useEffect(() => {
    if (!regularTaskId.trim()) return;
    const selectedId = Number(regularTaskId);
    if (!Number.isFinite(selectedId) || selectedId <= 0) return;
    if (!templateOptions.some((t) => t.regular_task_id === selectedId)) {
      setRegularTaskId("");
    }
  }, [templateOptions, regularTaskId]);

  React.useEffect(() => {
    if (!orgUnitId.trim()) return;
    const selectedId = Number(orgUnitId);
    if (!Number.isFinite(selectedId) || selectedId <= 0) return;
    if (!filteredOwnerUnitOptions.some((u) => u.unit_id === selectedId)) {
      setOrgUnitId("");
    }
  }, [filteredOwnerUnitOptions, orgUnitId]);

  function handleScheduleTypeChange(next: CatchUpScheduleType) {
    setScheduleType(next);
    setPeriodKey(resolveDefaultPeriodKey(next));
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
              onChange={(e) => {
                setPeriodKey(e.target.value);
                resetWorkflow();
              }}
              data-testid="catch-up-period-select"
            >
              {periodOptions.map((opt) => (
                <option key={opt.key} value={opt.key}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-zinc-800 dark:text-zinc-200">Группа отделений (опционально)</span>
            <select
              className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
              value={orgGroup}
              onChange={(e) => {
                setOrgGroup(e.target.value as OrgGroupFilter);
                setOrgUnitId("");
                resetWorkflow();
              }}
              data-testid="catch-up-org-group"
            >
              {orgGroupOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-zinc-800 dark:text-zinc-200">
              {uiFieldLabel("owner_unit_id")} (опционально)
            </span>
            <select
              className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
              value={orgUnitId}
              onChange={(e) => {
                setOrgUnitId(e.target.value);
                resetWorkflow();
              }}
              disabled={ownerUnitLoading}
              data-testid="catch-up-org-unit"
            >
              <option value="">Все отделения в группе</option>
              {unitSelectGroups.map((group) => (
                <optgroup key={group.key} label={group.label}>
                  {group.items.map((u) => (
                    <option key={u.unit_id} value={String(u.unit_id)}>
                      {`${u.name} (#${u.unit_id})`}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            {ownerUnitLoadError ? (
              <span className="text-xs text-red-600 dark:text-red-400">{ownerUnitLoadError}</span>
            ) : null}
          </label>

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-zinc-800 dark:text-zinc-200">
              {catchUpUiLabel("executor_role_id")} (опционально)
            </span>
            <select
              className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
              value={executorRoleId}
              onChange={(e) => {
                setExecutorRoleId(e.target.value);
                resetWorkflow();
              }}
              disabled={rolesLoading}
              data-testid="catch-up-executor"
            >
              <option value="">Все роли</option>
              {roleOptions.map((role) => (
                <option key={role.role_id} value={String(role.role_id)}>
                  {directoryRoleLabel(role)}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
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
