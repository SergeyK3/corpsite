"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import React from "react";

import {
  apiCatchUpRegularTasks,
  apiFetchJson,
  type CatchUpPreset,
  type CatchUpRegularTasksParams,
} from "@/lib/api";
import {
  buildOrgUnitSelectGroups,
  loadOrgUnitSelectOptions,
  type OrgUnitSelectOption,
} from "@/lib/orgUnitsSelect";
import {
  formatThrownError,
  runTitleLabel,
  scheduleTypeLabel,
  uiFieldLabel,
} from "@/lib/i18n";

type OrgGroupFilter = "all" | "clinical" | "paraclinical" | "admin";

type DeptGroupRow = {
  group_id: number;
  group_name: string;
};

type DeptGroupsResponse = {
  items?: DeptGroupRow[];
};

const ORG_GROUP_OPTIONS: Array<{ value: OrgGroupFilter; label: string }> = [
  { value: "all", label: "Все группы отделений" },
  { value: "clinical", label: "Клинические" },
  { value: "paraclinical", label: "Параклинические" },
  { value: "admin", label: "Административно-хозяйственные" },
];

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

type CatchUpResult = {
  run_id: number;
  dry_run: boolean;
  resolved?: {
    preset?: string;
    run_for_date?: string;
    schedule_type?: string | null;
    org_group_id?: number | null;
    org_unit_id?: number | null;
    templates_in_scope?: number;
  };
  stats?: {
    templates_total?: number;
    templates_due?: number;
    created?: number;
    deduped?: number;
    errors?: number;
  };
};

function presetLabel(p: CatchUpPreset): string {
  if (p === "past_week") return `Прошлая неделя (${scheduleTypeLabel("weekly")})`;
  if (p === "past_month") return `Прошлый месяц (${scheduleTypeLabel("monthly")})`;
  return "Ручная дата";
}

export default function CatchUpRunClient() {
  const sp = useSearchParams();
  const orgUnitFromUrl = sp.get("org_unit_id") ?? "";

  const [preset, setPreset] = React.useState<CatchUpPreset>("past_week");
  const [manualDate, setManualDate] = React.useState("");
  const [orgGroup, setOrgGroup] = React.useState<OrgGroupFilter>("all");
  const [deptGroups, setDeptGroups] = React.useState<DeptGroupRow[]>([]);
  const [orgUnitId, setOrgUnitId] = React.useState(orgUnitFromUrl);
  const [ownerUnitOptions, setOwnerUnitOptions] = React.useState<OrgUnitSelectOption[]>([]);
  const [ownerUnitLoading, setOwnerUnitLoading] = React.useState(false);
  const [ownerUnitLoadError, setOwnerUnitLoadError] = React.useState<string | null>(null);

  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const [previewResult, setPreviewResult] = React.useState<CatchUpResult | null>(null);
  const [liveResult, setLiveResult] = React.useState<CatchUpResult | null>(null);

  const selectedOrgGroupId = React.useMemo(
    () => resolveOrgGroupId(orgGroup, deptGroups),
    [orgGroup, deptGroups],
  );

  const selectedOrgGroupLabel = React.useMemo(() => {
    return ORG_GROUP_OPTIONS.find((x) => x.value === orgGroup)?.label ?? null;
  }, [orgGroup]);

  const parsedOrgUnitId = React.useMemo(() => {
    const s = (orgUnitId || orgUnitFromUrl).trim();
    if (!s) return null;
    const n = Number(s);
    return Number.isFinite(n) && n > 0 ? Math.trunc(n) : null;
  }, [orgUnitId, orgUnitFromUrl]);

  React.useEffect(() => {
    setOrgUnitId(orgUnitFromUrl);
  }, [orgUnitFromUrl]);

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
    if (!orgUnitId.trim()) return;
    const selectedId = Number(orgUnitId);
    if (!Number.isFinite(selectedId) || selectedId <= 0) return;
    if (!filteredOwnerUnitOptions.some((u) => u.unit_id === selectedId)) {
      setOrgUnitId("");
    }
  }, [filteredOwnerUnitOptions, orgUnitId]);

  const buildPayload = React.useCallback(
    (dryRun: boolean): CatchUpRegularTasksParams => {
      const payload: CatchUpRegularTasksParams = {
        dry_run: dryRun,
        preset,
      };
      if (preset === "manual") {
        payload.run_for_date = manualDate.trim();
      }
      if (selectedOrgGroupId != null) {
        payload.org_group_id = selectedOrgGroupId;
      }
      if (parsedOrgUnitId != null) {
        payload.org_unit_id = parsedOrgUnitId;
      }
      return payload;
    },
    [preset, manualDate, selectedOrgGroupId, parsedOrgUnitId],
  );

  const validateForm = React.useCallback((): string | null => {
    if (preset === "manual" && !manualDate.trim()) {
      return "Укажите дату для ручного пресета.";
    }
    if (preset === "manual" && Number.isNaN(Date.parse(manualDate.trim()))) {
      return "Некорректная дата (ожидается YYYY-MM-DD).";
    }
    return null;
  }, [preset, manualDate]);

  async function handlePreview() {
    const validation = validateForm();
    if (validation) {
      setSubmitError(validation);
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    setPreviewResult(null);

    try {
      const result = await apiCatchUpRegularTasks(buildPayload(true));
      setPreviewResult(result);
    } catch (err) {
      setSubmitError(formatThrownError(err, { fallback: "Не удалось выполнить пробный прогон." }));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleLiveRun() {
    const validation = validateForm();
    if (validation) {
      setSubmitError(validation);
      return;
    }
    if (!previewResult) {
      setSubmitError("Сначала выполните пробный прогон.");
      return;
    }

    const ok = window.confirm(
      "Боевой догоняющий запуск создаст задачи в базе.\n\nПеред этим на VPS должен быть выполнен backup (scripts/backup_db.sh).\n\nПродолжить?",
    );
    if (!ok) return;

    setSubmitting(true);
    setSubmitError(null);

    try {
      const result = await apiCatchUpRegularTasks(buildPayload(false));
      setLiveResult(result);
    } catch (err) {
      setSubmitError(formatThrownError(err, { fallback: "Не удалось выполнить боевой прогон." }));
    } finally {
      setSubmitting(false);
    }
  }

  function renderResult(title: string, result: CatchUpResult | null) {
    if (!result) return null;
    const resolved = result.resolved ?? {};
    const stats = result.stats ?? {};

    return (
      <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white/50 dark:bg-zinc-900/50 px-4 py-3 text-sm">
        <div className="font-medium text-zinc-900 dark:text-zinc-50">{title}</div>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-zinc-700 dark:text-zinc-300">
          <div>
            <span className="text-zinc-500 dark:text-zinc-400">{uiFieldLabel("run_id")}:</span> {result.run_id}
          </div>
          <div>
            <span className="text-zinc-500 dark:text-zinc-400">дата:</span> {resolved.run_for_date ?? "—"}
          </div>
          <div>
            <span className="text-zinc-500 dark:text-zinc-400">тип:</span>{" "}
            {scheduleTypeLabel(resolved.schedule_type) || "—"}
          </div>
          <div>
            <span className="text-zinc-500 dark:text-zinc-400">шаблонов:</span>{" "}
            {resolved.templates_in_scope ?? stats.templates_total ?? 0}
          </div>
          <div>
            <span className="text-zinc-500 dark:text-zinc-400">создано:</span> {stats.created ?? 0}
          </div>
          <div>
            <span className="text-zinc-500 dark:text-zinc-400">дедуп:</span> {stats.deduped ?? 0}
          </div>
          <div>
            <span className="text-zinc-500 dark:text-zinc-400">ошибки:</span> {stats.errors ?? 0}
          </div>
        </div>
        {result.run_id ? (
          <div className="mt-2">
            <Link
              href={`/regular-task-runs?run_id=${result.run_id}`}
              className="text-blue-600 hover:underline dark:text-blue-400"
            >
              Открыть журнал — {runTitleLabel(result.run_id)}
            </Link>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 md:p-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">Догоняющий запуск</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Разовый прогон регулярных задач для обучения персонала: один run, фильтр по отделению, все активные
          шаблоны в scope (без проверки due-check). Сначала пробный прогон, затем боевой — после backup на VPS.
        </p>
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
        <div className="grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-zinc-800 dark:text-zinc-200">Период</span>
            <select
              className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
              value={preset}
              onChange={(e) => setPreset(e.target.value as CatchUpPreset)}
            >
              <option value="past_week">{presetLabel("past_week")}</option>
              <option value="past_month">{presetLabel("past_month")}</option>
              <option value="manual">{presetLabel("manual")}</option>
            </select>
          </label>

          {preset === "manual" ? (
            <label className="flex flex-col gap-1 text-sm">
              <span className="font-medium text-zinc-800 dark:text-zinc-200">Дата (YYYY-MM-DD)</span>
              <input
                type="date"
                className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
                value={manualDate}
                onChange={(e) => setManualDate(e.target.value)}
              />
            </label>
          ) : (
            <div className="flex flex-col justify-end text-sm text-zinc-600 dark:text-zinc-400">
              Опорная дата вычисляется на backend автоматически.
            </div>
          )}

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-zinc-800 dark:text-zinc-200">Группа отделений</span>
            <select
              className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
              value={orgGroup}
              onChange={(e) => {
                setOrgGroup(e.target.value as OrgGroupFilter);
                setOrgUnitId("");
                setPreviewResult(null);
                setLiveResult(null);
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
            <span className="font-medium text-zinc-800 dark:text-zinc-200">{uiFieldLabel("owner_unit_id")}</span>
            <select
              className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
              value={orgUnitId}
              onChange={(e) => setOrgUnitId(e.target.value)}
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
            {ownerUnitLoading ? (
              <span className="text-xs text-zinc-500 dark:text-zinc-400">Загрузка отделений...</span>
            ) : null}
            {ownerUnitLoadError ? (
              <span className="text-xs text-red-600 dark:text-red-400">{ownerUnitLoadError}</span>
            ) : null}
            {!ownerUnitLoading && !ownerUnitLoadError && filteredOwnerUnitOptions.length === 0 ? (
              <span className="text-xs text-amber-700 dark:text-amber-300">
                {ownerUnitOptions.length === 0
                  ? "Список отделений пуст. Откройте /directory/org-units под admin и проверьте, что API возвращает items."
                  : selectedOrgGroupId != null
                    ? `В группе «${selectedOrgGroupLabel}» нет отделений (загружено всего: ${ownerUnitOptions.length}).`
                    : "Нет отделений для выбора."}
              </span>
            ) : null}
            {!ownerUnitLoading && !ownerUnitLoadError && filteredOwnerUnitOptions.length > 0 ? (
              <span className="text-xs text-zinc-500 dark:text-zinc-400">
                Доступно отделений: {filteredOwnerUnitOptions.length}
              </span>
            ) : null}
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={submitting}
            onClick={handlePreview}
            className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-4 py-2 text-sm font-medium text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
          >
            {submitting ? "Выполняется..." : "Пробный прогон"}
          </button>
          <button
            type="button"
            disabled={submitting || !previewResult}
            onClick={handleLiveRun}
            className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Боевой прогон
          </button>
        </div>

        {submitError ? (
          <div className="mt-3 rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 p-3 text-sm text-red-700 dark:text-red-300">
            {submitError}
          </div>
        ) : null}
      </section>

      {renderResult("Результат пробного прогона", previewResult)}
      {renderResult("Результат боевого прогона", liveResult)}
    </div>
  );
}
