"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import React from "react";

import CatchUpReviewPanel from "./CatchUpReviewPanel";

import {
  apiCatchUpRegularTasks,
  apiFetchJson,
  apiGetRegularTaskRunItems,
  type CatchUpPreset,
  type CatchUpRegularTasksParams,
  type CatchUpRegularTasksResult,
} from "@/lib/api";
import {
  buildCatchUpPayload,
  pastWeekPresetHint,
  payloadsEquivalent,
  resolveDefaultScheduleType,
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
  formatThrownError,
  scheduleTypeLabel,
  uiFieldLabel,
} from "@/lib/i18n";
import type { RegularTaskRunItemRow } from "@/lib/regularTaskRunJournal";

type OrgGroupFilter = "all" | "clinical" | "paraclinical" | "admin";

type DeptGroupRow = {
  group_id: number;
  group_name: string;
};

type DeptGroupsResponse = {
  items?: DeptGroupRow[];
};

type RoleRow = {
  role_id: number;
  name?: string | null;
  code?: string | null;
};

type RolesResponse = {
  items?: RoleRow[];
};

const ORG_GROUP_OPTIONS: Array<{ value: OrgGroupFilter; label: string }> = [
  { value: "all", label: "Все группы отделений" },
  { value: "clinical", label: "Клинические" },
  { value: "paraclinical", label: "Параклинические" },
  { value: "admin", label: "Административно-хозяйственные" },
];

const SCHEDULE_TYPE_OPTIONS: Array<{ value: CatchUpScheduleType; label: string }> = [
  { value: "weekly", label: scheduleTypeLabel("weekly") },
  { value: "monthly", label: scheduleTypeLabel("monthly") },
  { value: "yearly", label: scheduleTypeLabel("yearly") },
];

const WORKFLOW_STEPS = [
  { id: 1, label: "Dry Run" },
  { id: 2, label: "Review" },
  { id: 3, label: "Confirm" },
  { id: 4, label: "Execute" },
  { id: 5, label: "Journal" },
] as const;

function readEnvGroupId(name: string, fallback: number): number {
  const raw = String(process.env[name] ?? "").trim();
  if (!raw) return fallback;
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  return n;
}

const ENV_ORG_GROUP_IDS: Record<Exclude<OrgGroupFilter, "all">, number> = {
  clinical: readEnvGroupId("NEXT_PUBLIC_ORG_GROUP_ID_CLINICAL", 1),
  paraclinical: readEnvGroupId("NEXT_PUBLIC_ORG_GROUP_ID_PARACLINICAL", 2),
  admin: readEnvGroupId("NEXT_PUBLIC_ORG_GROUP_ID_ADMIN", 3),
};

const ORG_GROUP_NAME_PATTERNS: Record<Exclude<OrgGroupFilter, "all">, RegExp> = {
  clinical: /клинич/i,
  paraclinical: /параклинич/i,
  admin: /адм|хоз/i,
};

function resolveOrgGroupId(filter: OrgGroupFilter, deptGroups: DeptGroupRow[]): number | null {
  if (filter === "all") return null;

  const envId = ENV_ORG_GROUP_IDS[filter];
  if (deptGroups.some((g) => g.group_id === envId)) return envId;

  const byName = deptGroups.find((g) => ORG_GROUP_NAME_PATTERNS[filter].test(g.group_name));
  if (byName) return byName.group_id;

  return envId;
}

function presetLabel(p: CatchUpPreset): string {
  if (p === "past_week") return `Прошлая неделя (${scheduleTypeLabel("weekly")})`;
  if (p === "past_month") return `Прошлый месяц (${scheduleTypeLabel("monthly")})`;
  return "Ручная дата";
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
            {step.id}. {step.label}
          </li>
        );
      })}
    </ol>
  );
}

export default function CatchUpRunClient() {
  const sp = useSearchParams();
  const orgUnitFromUrl = sp.get("org_unit_id") ?? "";

  const [preset, setPreset] = React.useState<CatchUpPreset>("past_week");
  const [manualDate, setManualDate] = React.useState("");
  const [scheduleType, setScheduleType] = React.useState<CatchUpScheduleType>("weekly");
  const [orgGroup, setOrgGroup] = React.useState<OrgGroupFilter>("all");
  const [deptGroups, setDeptGroups] = React.useState<DeptGroupRow[]>([]);
  const [orgUnitId, setOrgUnitId] = React.useState(orgUnitFromUrl);
  const [executorRoleId, setExecutorRoleId] = React.useState("");
  const [roleOptions, setRoleOptions] = React.useState<RoleRow[]>([]);
  const [rolesLoading, setRolesLoading] = React.useState(false);
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

  const formState = React.useMemo<CatchUpFormState>(
    () => ({
      preset,
      manualDate,
      scheduleType,
      orgGroupId: selectedOrgGroupId,
      orgUnitId: parsedOrgUnitId,
      executorRoleId: parsedExecutorRoleId,
    }),
    [preset, manualDate, scheduleType, selectedOrgGroupId, parsedOrgUnitId, parsedExecutorRoleId],
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

  const groupLabelById = React.useMemo(() => {
    const map = new Map<number, string>();
    for (const opt of ORG_GROUP_OPTIONS) {
      if (opt.value === "all") continue;
      const gid = resolveOrgGroupId(opt.value, deptGroups);
      if (gid != null) map.set(gid, opt.label);
    }
    for (const g of deptGroups) {
      if (!map.has(g.group_id)) map.set(g.group_id, g.group_name);
    }
    return map;
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
          query: { status: "active", limit: 200 },
        });
        const rows = Array.isArray(data?.items) ? data.items : [];
        if (!cancelled) {
          setRoleOptions(
            rows
              .map((r) => ({
                role_id: Number(r.role_id),
                name: r.name ?? null,
                code: r.code ?? null,
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
    if (!orgUnitId.trim()) return;
    const selectedId = Number(orgUnitId);
    if (!Number.isFinite(selectedId) || selectedId <= 0) return;
    if (!filteredOwnerUnitOptions.some((u) => u.unit_id === selectedId)) {
      setOrgUnitId("");
    }
  }, [filteredOwnerUnitOptions, orgUnitId]);

  function handlePresetChange(next: CatchUpPreset) {
    setPreset(next);
    setScheduleType(resolveDefaultScheduleType(next));
    resetWorkflow();
  }

  async function loadRunItems(runId: number): Promise<RegularTaskRunItemRow[]> {
    const data = await apiGetRegularTaskRunItems({ run_id: runId });
    return data as RegularTaskRunItemRow[];
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
          Безопасный workflow: пробный прогон → проверка периода и items → подтверждение → боевой запуск →
          журнал. SSH и curl не требуются.
        </p>
        <WorkflowStepper activeStep={activeStep} />
        <div className="flex flex-wrap gap-2 text-sm">
          <Link href="/admin/regular-tasks" className="text-blue-600 hover:underline dark:text-blue-400">
            Шаблоны регулярных задач
          </Link>
          <span className="text-zinc-400">·</span>
          <Link href="/regular-task-runs" className="text-blue-600 hover:underline dark:text-blue-400">
            Журнал запусков
          </Link>
        </div>
      </div>

      <section className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-4 shadow-sm">
        <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">1. Параметры и пробный прогон</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-zinc-800 dark:text-zinc-200">Период (preset)</span>
            <select
              className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
              value={preset}
              onChange={(e) => handlePresetChange(e.target.value as CatchUpPreset)}
            >
              <option value="past_week">{presetLabel("past_week")}</option>
              <option value="past_month">{presetLabel("past_month")}</option>
              <option value="manual">{presetLabel("manual")}</option>
            </select>
            {preset === "past_week" ? (
              <span className="text-xs text-zinc-500 dark:text-zinc-400">{pastWeekPresetHint()}</span>
            ) : null}
          </label>

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-zinc-800 dark:text-zinc-200">schedule_type</span>
            <select
              className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
              value={scheduleType}
              onChange={(e) => {
                setScheduleType(e.target.value as CatchUpScheduleType);
                resetWorkflow();
              }}
            >
              {SCHEDULE_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          {preset === "manual" ? (
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-zinc-800 dark:text-zinc-200">run_for_date</span>
              <input
                type="date"
                className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
                value={manualDate}
                onChange={(e) => {
                  setManualDate(e.target.value);
                  resetWorkflow();
                }}
              />
            </label>
          ) : (
            <div className="flex flex-col justify-end text-sm text-zinc-600 dark:text-zinc-400">
              run_for_date вычисляется на backend автоматически.
            </div>
          )}

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
            >
              {ORG_GROUP_OPTIONS.map((opt) => (
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
              {uiFieldLabel("executor_role_id")} (опционально)
            </span>
            <select
              className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
              value={executorRoleId}
              onChange={(e) => {
                setExecutorRoleId(e.target.value);
                resetWorkflow();
              }}
              disabled={rolesLoading}
            >
              <option value="">Все роли</option>
              {roleOptions.map((role) => (
                <option key={role.role_id} value={String(role.role_id)}>
                  {(role.name || role.code || `#${role.role_id}`) + ` (#${role.role_id})`}
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
            {submitting ? "Выполняется..." : "Пробный прогон"}
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
            title="2. Результат пробного прогона"
            result={previewResult}
            items={previewItems}
            isDryRunPreview
            showJournalLink={false}
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
            <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">3. Подтверждение перед боевым запуском</h2>
            <p className="mt-2 text-sm text-amber-800 dark:text-amber-200">
              Рекомендуется выполнить резервную копию БД перед боевым запуском (на VPS:{" "}
              <code className="rounded bg-amber-100/80 px-1 dark:bg-amber-950/50">scripts/backup_db.sh</code>
              ).
            </p>
            <label className="mt-4 flex items-start gap-2 text-sm text-zinc-800 dark:text-zinc-200">
              <input
                type="checkbox"
                className="mt-1"
                checked={reviewConfirmed}
                onChange={(e) => setReviewConfirmed(e.target.checked)}
                data-testid="catch-up-review-confirmed"
              />
              <span>Я проверил результат пробного прогона (период, шаблоны, due_date).</span>
            </label>

            <div className="mt-4">
              <button
                type="button"
                disabled={submitting || !reviewConfirmed || payloadDrift}
                onClick={handleLiveRun}
                className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                data-testid="catch-up-execute"
              >
                {submitting ? "Выполняется..." : "Выполнить боевой запуск"}
              </button>
            </div>
          </section>
        </>
      ) : null}

      {liveResult ? (
        <CatchUpReviewPanel
          title="4–5. Результат боевого прогона"
          result={liveResult}
          items={liveItems}
          isDryRunPreview={false}
          showJournalLink
        />
      ) : null}
    </div>
  );
}
