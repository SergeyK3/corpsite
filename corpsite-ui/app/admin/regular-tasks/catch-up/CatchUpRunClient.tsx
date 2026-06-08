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

type DeptGroupRow = {
  group_id: number;
  group_name: string;
};

type DeptGroupsResponse = {
  items?: DeptGroupRow[];
};

type OrgUnitRow = {
  id?: number | string;
  unit_id?: number;
  unitId?: number;
  parent_id?: number | string | null;
  parent_unit_id?: number | null;
  name?: string | null;
  title?: string | null;
  code?: string | null;
  group_id?: number | null;
  groupId?: number | null;
};

type OrgUnitOption = {
  unit_id: number;
  name: string;
  group_id?: number | null;
};

type OrgUnitsListResponse = {
  items?: OrgUnitRow[];
};

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

function unitIdOf(row: OrgUnitRow): number | null {
  const direct = row.unit_id ?? row.unitId;
  if (typeof direct === "number" && Number.isFinite(direct) && direct > 0) return direct;
  const parsed = Number(row.id);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function unitNameOf(row: OrgUnitRow): string {
  const name = String(row.title ?? row.name ?? row.code ?? "").trim();
  const id = unitIdOf(row);
  return name || (id != null ? `#${id}` : "—");
}

function ownGroupId(row: OrgUnitRow): number | null {
  const g = row.group_id ?? row.groupId;
  if (typeof g === "number" && Number.isFinite(g) && g > 0) return g;
  return null;
}

function dedupeOrgUnitOptions(items: OrgUnitOption[]): OrgUnitOption[] {
  const seen = new Set<number>();
  return items
    .filter((x) => {
      if (seen.has(x.unit_id)) return false;
      seen.add(x.unit_id);
      return true;
    })
    .sort((a, b) => a.name.localeCompare(b.name, "ru"));
}

function flattenOrgUnitTree(nodes: unknown[], inheritedGroupId: number | null = null): OrgUnitOption[] {
  const out: OrgUnitOption[] = [];

  const walk = (list: unknown[], parentGroupId: number | null) => {
    for (const raw of list) {
      const node = raw as OrgUnitRow & { children?: unknown[] };
      const unitId = unitIdOf(node);
      const effectiveGroup = ownGroupId(node) ?? parentGroupId;
      if (unitId != null) {
        out.push({
          unit_id: unitId,
          name: unitNameOf(node),
          group_id: effectiveGroup,
        });
      }
      if (Array.isArray(node.children) && node.children.length > 0) {
        walk(node.children, effectiveGroup);
      }
    }
  };

  walk(nodes, inheritedGroupId);
  return dedupeOrgUnitOptions(out);
}

function enrichFlatOrgUnitsWithInheritedGroup(rows: OrgUnitRow[]): OrgUnitOption[] {
  const byId = new Map<number, OrgUnitRow>();
  for (const row of rows) {
    const id = unitIdOf(row);
    if (id != null) byId.set(id, row);
  }

  const resolveGroup = (id: number, seen = new Set<number>()): number | null => {
    if (seen.has(id)) return null;
    seen.add(id);
    const row = byId.get(id);
    if (!row) return null;
    const own = ownGroupId(row);
    if (own != null) return own;
    const parentRaw = row.parent_unit_id ?? row.parent_id;
    const parentId = Number(parentRaw);
    if (Number.isFinite(parentId) && parentId > 0) return resolveGroup(parentId, seen);
    return null;
  };

  return dedupeOrgUnitOptions(
    rows.flatMap((row): OrgUnitOption[] => {
      const unitId = unitIdOf(row);
      if (unitId == null) return [];
      return [
        {
          unit_id: unitId,
          name: unitNameOf(row),
          group_id: resolveGroup(unitId),
        },
      ];
    }),
  );
}

async function loadOrgUnitOptions(): Promise<OrgUnitOption[]> {
  const tree = await apiFetchJson<{ items?: unknown[] }>("/directory/org-units/tree", {
    query: { status: "active" },
  });
  const nodes = Array.isArray(tree?.items) ? tree.items : [];
  let options = flattenOrgUnitTree(nodes);
  if (options.length > 0) return options;

  const flat = await apiFetchJson<OrgUnitsListResponse>("/directory/org-units", {
    query: { status: "active" },
  });
  const rows = Array.isArray(flat?.items) ? flat.items : [];
  return enrichFlatOrgUnitsWithInheritedGroup(rows);
}

function errorText(err: unknown, fallback: string): string {
  if (err instanceof Error && err.message) return err.message;
  const detail =
    (err as { details?: { detail?: unknown }; detail?: unknown })?.details?.detail ??
    (err as { detail?: unknown })?.detail;
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  return fallback;
}

function presetLabel(p: CatchUpPreset): string {
  if (p === "past_week") return "Прошлая неделя (weekly)";
  if (p === "past_month") return "Прошлый месяц (monthly)";
  return "Ручная дата";
}

export default function CatchUpRunClient() {
  const sp = useSearchParams();
  const orgUnitFromUrl = sp.get("org_unit_id") ?? "";

  const [preset, setPreset] = React.useState<CatchUpPreset>("past_week");
  const [manualDate, setManualDate] = React.useState("");
  const [orgGroup, setOrgGroup] = React.useState<string>("all");
  const [deptGroups, setDeptGroups] = React.useState<DeptGroupRow[]>([]);
  const [deptGroupsLoading, setDeptGroupsLoading] = React.useState(false);
  const [orgUnitId, setOrgUnitId] = React.useState(orgUnitFromUrl);
  const [ownerUnitOptions, setOwnerUnitOptions] = React.useState<OrgUnitOption[]>([]);
  const [ownerUnitLoading, setOwnerUnitLoading] = React.useState(false);
  const [ownerUnitLoadError, setOwnerUnitLoadError] = React.useState<string | null>(null);

  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const [previewResult, setPreviewResult] = React.useState<CatchUpResult | null>(null);
  const [liveResult, setLiveResult] = React.useState<CatchUpResult | null>(null);

  const selectedOrgGroupId = React.useMemo(() => {
    if (orgGroup === "all") return null;
    const n = Number(orgGroup);
    return Number.isFinite(n) && n > 0 ? Math.trunc(n) : null;
  }, [orgGroup]);

  const selectedOrgGroupLabel = React.useMemo(() => {
    if (selectedOrgGroupId == null) return null;
    return deptGroups.find((g) => g.group_id === selectedOrgGroupId)?.group_name ?? `#${selectedOrgGroupId}`;
  }, [deptGroups, selectedOrgGroupId]);

  const parsedOrgUnitId = React.useMemo(() => {
    const s = (orgUnitId || orgUnitFromUrl).trim();
    if (!s) return null;
    const n = Number(s);
    return Number.isFinite(n) && n > 0 ? Math.trunc(n) : null;
  }, [orgUnitId, orgUnitFromUrl]);

  React.useEffect(() => {
    setOrgUnitId(orgUnitFromUrl);
  }, [orgUnitFromUrl]);

  const filteredOwnerUnitOptions = React.useMemo(() => {
    if (selectedOrgGroupId == null) return ownerUnitOptions;
    return ownerUnitOptions.filter((u) => Number(u.group_id) === Number(selectedOrgGroupId));
  }, [ownerUnitOptions, selectedOrgGroupId]);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      setDeptGroupsLoading(true);
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
              .filter((g) => Number.isFinite(g.group_id) && g.group_id > 0)
              .sort((a, b) => a.group_name.localeCompare(b.group_name, "ru")),
          );
        }
      } catch {
        if (!cancelled) setDeptGroups([]);
      } finally {
        if (!cancelled) setDeptGroupsLoading(false);
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
        const options = await loadOrgUnitOptions();
        if (!cancelled) setOwnerUnitOptions(options);
      } catch (err) {
        if (!cancelled) {
          setOwnerUnitOptions([]);
          setOwnerUnitLoadError(errorText(err, "Не удалось загрузить список отделений."));
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
      setSubmitError(errorText(err, "Не удалось выполнить пробный прогон."));
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
      setSubmitError(errorText(err, "Не удалось выполнить боевой прогон."));
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
            <span className="text-zinc-500 dark:text-zinc-400">run_id:</span> {result.run_id}
          </div>
          <div>
            <span className="text-zinc-500 dark:text-zinc-400">дата:</span> {resolved.run_for_date ?? "—"}
          </div>
          <div>
            <span className="text-zinc-500 dark:text-zinc-400">тип:</span> {resolved.schedule_type ?? "—"}
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
              Открыть журнал запуска #{result.run_id}
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
                setOrgGroup(e.target.value);
                setOrgUnitId("");
                setPreviewResult(null);
                setLiveResult(null);
              }}
              disabled={deptGroupsLoading}
            >
              <option value="all">Все группы отделений</option>
              {deptGroups.map((g) => (
                <option key={g.group_id} value={String(g.group_id)}>
                  {g.group_name}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium text-zinc-800 dark:text-zinc-200">Отделение (owner_unit_id)</span>
            <select
              className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-zinc-900 dark:text-zinc-50"
              value={orgUnitId}
              onChange={(e) => setOrgUnitId(e.target.value)}
              disabled={ownerUnitLoading}
            >
              <option value="">Все отделения в группе</option>
              {filteredOwnerUnitOptions.map((u) => (
                <option key={u.unit_id} value={String(u.unit_id)}>
                  {`${u.name} (#${u.unit_id})`}
                </option>
              ))}
            </select>
            {ownerUnitLoadError ? (
              <span className="text-xs text-red-600 dark:text-red-400">{ownerUnitLoadError}</span>
            ) : null}
            {!ownerUnitLoading && !ownerUnitLoadError && filteredOwnerUnitOptions.length === 0 ? (
              <span className="text-xs text-amber-700 dark:text-amber-300">
                {ownerUnitOptions.length === 0
                  ? "Список отделений пуст. Проверьте справочник «Отделения» и права admin."
                  : selectedOrgGroupId != null
                    ? `В группе «${selectedOrgGroupLabel}» нет отделений (загружено всего: ${ownerUnitOptions.length}). Проверьте group_id у отделений в справочнике.`
                    : "Нет отделений для выбора."}
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
