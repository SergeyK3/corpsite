// FILE: corpsite-ui/app/regular-tasks/_components/RegularTasksAdminClient.tsx
"use client";

import * as React from "react";
import { apiFetchJson } from "../../../lib/api";
import TemplateDrawer from "../../regular-tasks/_components/TemplateDrawer";
import TemplateForm, { type TemplateFormValues } from "../../regular-tasks/_components/TemplateForm";

type RegularTaskItem = {
  regular_task_id: number;
  code?: string | null;
  title: string;
  description?: string | null;
  periodicity?: string | null;
  schedule_type?: string | null;
  schedule_params?: Record<string, unknown> | null;
  executor_role_id?: number | null;
  assignment_scope?: string | null;
  create_offset_days?: number | null;
  due_offset_days?: number | null;
  is_active: boolean;
  created_by_user_id?: number | null;
  updated_at?: string | null;
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
type DrawerMode = "create" | "view" | "edit";
type OrgGroupFilter = "all" | "clinical" | "paraclinical" | "admin";

function readEnvGroupId(name: string, fallback: number): number {
  const raw = String(process.env[name] ?? "").trim();
  if (!raw) return fallback;
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return fallback;
  return n;
}

const ORG_GROUP_ID_CLINICAL = readEnvGroupId("NEXT_PUBLIC_ORG_GROUP_ID_CLINICAL", 1);
const ORG_GROUP_ID_PARACLINICAL = readEnvGroupId("NEXT_PUBLIC_ORG_GROUP_ID_PARACLINICAL", 2);
const ORG_GROUP_ID_ADMIN = readEnvGroupId("NEXT_PUBLIC_ORG_GROUP_ID_ADMIN", 3);

const ORG_GROUP_OPTIONS: Array<{ value: OrgGroupFilter; label: string; id?: number }> = [
  { value: "all", label: "Все группы" },
  { value: "clinical", label: "Клинические", id: ORG_GROUP_ID_CLINICAL },
  { value: "paraclinical", label: "Параклинические", id: ORG_GROUP_ID_PARACLINICAL },
  { value: "admin", label: "Административно-хозяйственные", id: ORG_GROUP_ID_ADMIN },
];

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

function errorText(err: unknown, fallback: string): string {
  if (err instanceof Error && err.message) return err.message;
  const detail =
    (err as { details?: { detail?: unknown }; detail?: unknown })?.details?.detail ??
    (err as { detail?: unknown })?.detail;

  if (typeof detail === "string" && detail.trim()) return detail.trim();
  return fallback;
}

function prettyJson(value: unknown): string {
  try {
    if (value === null || value === undefined) return "{}";
    if (typeof value === "string") return value.trim() || "{}";
    return JSON.stringify(value, null, 2);
  } catch {
    return "{}";
  }
}

function parseJsonObject(text: string): { value: Record<string, unknown> | null; error: string | null } {
  const s = String(text ?? "").trim();
  if (!s) return { value: {}, error: null };

  try {
    const parsed = JSON.parse(s);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { value: null, error: "schedule_params должен быть JSON-объектом." };
    }
    return { value: parsed as Record<string, unknown>, error: null };
  } catch {
    return { value: null, error: "schedule_params содержит некорректный JSON." };
  }
}

function toNullableInt(text: string): number | null {
  const s = String(text ?? "").trim();
  if (!s) return null;
  const n = Number(s);
  if (!Number.isFinite(n)) return null;
  return Math.trunc(n);
}

function normalizeTemplateList(data: RegularTasksListResponse | RegularTaskItem[]): RegularTaskItem[] {
  if (Array.isArray(data)) return data;
  return Array.isArray(data?.items) ? data.items : [];
}

function normalizeText(value: string): string {
  return String(value || "").toLowerCase().replace(/ё/g, "е").trim();
}

function matchesSearch(item: RegularTaskItem, q: string): boolean {
  const query = normalizeText(q);
  if (!query) return true;

  const haystack = normalizeText(
    [
      String(item.regular_task_id),
      item.title ?? "",
      item.description ?? "",
      item.schedule_type ?? "",
      item.assignment_scope ?? "",
      item.executor_role_id != null ? String(item.executor_role_id) : "",
    ].join(" "),
  );

  return haystack.includes(query);
}

function metricCard(label: string, value: React.ReactNode) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/40 px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-zinc-100">{value}</div>
    </div>
  );
}

export default function RegularTasksAdminClient() {
  const [activeTab, setActiveTab] = React.useState<MainTab>("templates");

  const [templates, setTemplates] = React.useState<RegularTaskItem[]>([]);
  const [templatesLoading, setTemplatesLoading] = React.useState(false);
  const [templatesError, setTemplatesError] = React.useState<string | null>(null);

  const [selectedTemplateId, setSelectedTemplateId] = React.useState<number | null>(null);
  const [selectedTemplate, setSelectedTemplate] = React.useState<RegularTaskItem | null>(null);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerMode, setDrawerMode] = React.useState<DrawerMode>("view");
  const [drawerLoading, setDrawerLoading] = React.useState(false);
  const [drawerError, setDrawerError] = React.useState<string | null>(null);
  const [drawerSaving, setDrawerSaving] = React.useState(false);

  const [runs, setRuns] = React.useState<RegularTaskRun[]>([]);
  const [runsLoading, setRunsLoading] = React.useState(false);
  const [runsError, setRunsError] = React.useState<string | null>(null);

  const [selectedRunId, setSelectedRunId] = React.useState<number | null>(null);
  const [runItems, setRunItems] = React.useState<RunItem[]>([]);
  const [runItemsLoading, setRunItemsLoading] = React.useState(false);
  const [runItemsError, setRunItemsError] = React.useState<string | null>(null);

  const [query, setQuery] = React.useState("");
  const [activeFilter, setActiveFilter] = React.useState<"all" | "active" | "inactive">("all");
  const [orgGroup, setOrgGroup] = React.useState<OrgGroupFilter>("all");

  const [runAtLocalIso, setRunAtLocalIso] = React.useState("");
  const [dryRun, setDryRun] = React.useState(true);
  const [runSubmitting, setRunSubmitting] = React.useState(false);
  const [runSubmitError, setRunSubmitError] = React.useState<string | null>(null);
  const [lastRunResult, setLastRunResult] = React.useState<RunResult | null>(null);

  const selectedOrgGroupId = React.useMemo(() => {
    const found = ORG_GROUP_OPTIONS.find((x) => x.value === orgGroup);
    return found?.id;
  }, [orgGroup]);

  const selectedOrgGroupLabel = React.useMemo(() => {
    const found = ORG_GROUP_OPTIONS.find((x) => x.value === orgGroup);
    return found?.label ?? "Все группы";
  }, [orgGroup]);

  const loadTemplates = React.useCallback(async () => {
    setTemplatesLoading(true);
    setTemplatesError(null);

    try {
      const data = await apiFetchJson<RegularTasksListResponse>("/regular-tasks", {
        query: {
          status: "all",
          limit: 200,
          offset: 0,
          org_group_id: selectedOrgGroupId ?? undefined,
        },
      });

      const rows = normalizeTemplateList(data);
      setTemplates(rows);

      if (
        selectedTemplateId != null &&
        drawerOpen &&
        drawerMode !== "create" &&
        !rows.some((x) => x.regular_task_id === selectedTemplateId)
      ) {
        setDrawerOpen(false);
        setDrawerMode("view");
        setSelectedTemplateId(null);
        setSelectedTemplate(null);
        setDrawerError(null);
      }
    } catch (err) {
      setTemplatesError(errorText(err, "Не удалось загрузить шаблоны."));
      setTemplates([]);
    } finally {
      setTemplatesLoading(false);
    }
  }, [selectedOrgGroupId, selectedTemplateId, drawerOpen, drawerMode]);

  const loadTemplateCard = React.useCallback(async (regularTaskId: number) => {
    setDrawerLoading(true);
    setDrawerError(null);

    try {
      const data = await apiFetchJson<RegularTaskItem>(`/regular-tasks/${regularTaskId}`);
      setSelectedTemplate(data);
    } catch (err) {
      setSelectedTemplate(null);
      setDrawerError(errorText(err, "Не удалось загрузить карточку шаблона."));
    } finally {
      setDrawerLoading(false);
    }
  }, []);

  const loadRuns = React.useCallback(async () => {
    setRunsLoading(true);
    setRunsError(null);

    try {
      const data = await apiFetchJson<RegularTaskRun[]>("/regular-task-runs", {
        query: {
          org_group_id: selectedOrgGroupId ?? undefined,
        },
      });
      const rows = Array.isArray(data) ? data : [];
      setRuns(rows);

      if (rows.length === 0) {
        setSelectedRunId(null);
        return;
      }

      if (selectedRunId == null || !rows.some((x) => x.run_id === selectedRunId)) {
        setSelectedRunId(rows[0].run_id);
      }
    } catch (err) {
      setRunsError(errorText(err, "Не удалось загрузить историю запусков."));
      setRuns([]);
      setSelectedRunId(null);
    } finally {
      setRunsLoading(false);
    }
  }, [selectedOrgGroupId, selectedRunId]);

  const loadRunItems = React.useCallback(
    async (runId: number) => {
      setRunItemsLoading(true);
      setRunItemsError(null);

      try {
        const data = await apiFetchJson<RunItem[]>(`/regular-task-runs/${runId}/items`, {
          query: {
            org_group_id: selectedOrgGroupId ?? undefined,
          },
        });
        setRunItems(Array.isArray(data) ? data : []);
      } catch (err) {
        setRunItemsError(errorText(err, "Не удалось загрузить детали запуска."));
        setRunItems([]);
      } finally {
        setRunItemsLoading(false);
      }
    },
    [selectedOrgGroupId],
  );

  React.useEffect(() => {
    void Promise.all([loadTemplates(), loadRuns()]);
  }, [loadTemplates, loadRuns]);

  React.useEffect(() => {
    if (selectedRunId == null) {
      setRunItems([]);
      return;
    }
    void loadRunItems(selectedRunId);
  }, [selectedRunId, loadRunItems]);

  const filteredTemplates = React.useMemo(() => {
    return templates.filter((item) => {
      if (activeFilter === "active" && !item.is_active) return false;
      if (activeFilter === "inactive" && item.is_active) return false;
      return matchesSearch(item, query);
    });
  }, [templates, query, activeFilter]);

  const templatesActiveCount = React.useMemo(() => templates.filter((x) => x.is_active).length, [templates]);

  const selectedTemplateFromList = React.useMemo(() => {
    if (selectedTemplateId == null) return null;
    return templates.find((x) => x.regular_task_id === selectedTemplateId) ?? null;
  }, [templates, selectedTemplateId]);

  const currentTemplate = selectedTemplate ?? selectedTemplateFromList ?? null;

  const initialFormValues = React.useMemo<TemplateFormValues>(() => {
    const x = currentTemplate ?? null;
    return {
      title: String(x?.title ?? ""),
      description: String(x?.description ?? ""),
      executor_role_id: x?.executor_role_id != null ? String(x.executor_role_id) : "",
      schedule_type: String(x?.schedule_type ?? ""),
      schedule_params: prettyJson(x?.schedule_params ?? {}),
      create_offset_days: String(x?.create_offset_days ?? 0),
      due_offset_days: String(x?.due_offset_days ?? 0),
    };
  }, [
    currentTemplate?.regular_task_id,
    currentTemplate?.title,
    currentTemplate?.description,
    currentTemplate?.executor_role_id,
    currentTemplate?.schedule_type,
    currentTemplate?.schedule_params,
    currentTemplate?.create_offset_days,
    currentTemplate?.due_offset_days,
  ]);

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
        body: payload,
      });

      setLastRunResult(result);
      setActiveTab("runs");
      await loadRuns();

      if (result?.run_id) {
        setSelectedRunId(result.run_id);
      }
    } catch (err) {
      setRunSubmitError(errorText(err, "Не удалось выполнить запуск."));
    } finally {
      setRunSubmitting(false);
    }
  }

  async function handleRefreshAll() {
    await Promise.all([loadTemplates(), loadRuns()]);

    if (selectedRunId != null) {
      await loadRunItems(selectedRunId);
    }

    if (selectedTemplateId != null && drawerOpen && drawerMode !== "create") {
      await loadTemplateCard(selectedTemplateId);
    }
  }

  function openCreateTemplate() {
    setDrawerMode("create");
    setDrawerError(null);
    setSelectedTemplateId(null);
    setSelectedTemplate(null);
    setDrawerOpen(true);
  }

  function openViewTemplate(item: RegularTaskItem) {
    setSelectedTemplateId(item.regular_task_id);
    setSelectedTemplate(item);
    setDrawerMode("view");
    setDrawerError(null);
    setDrawerOpen(true);
    void loadTemplateCard(item.regular_task_id);
  }

  function openEditTemplate(item: RegularTaskItem) {
    setSelectedTemplateId(item.regular_task_id);
    setSelectedTemplate(item);
    setDrawerMode("edit");
    setDrawerError(null);
    setDrawerOpen(true);
    void loadTemplateCard(item.regular_task_id);
  }

  function closeDrawer() {
    if (drawerSaving) return;
    setDrawerOpen(false);
    setDrawerMode("view");
    setDrawerError(null);
    setDrawerLoading(false);
  }

  function buildTemplatePayload(values: TemplateFormValues) {
    const parsed = parseJsonObject(values.schedule_params);

    return {
      payload: {
        title: String(values.title ?? "").trim(),
        description: String(values.description ?? "").trim() || null,
        executor_role_id: toNullableInt(values.executor_role_id),
        schedule_type: String(values.schedule_type ?? "").trim() || null,
        schedule_params: parsed.value,
        create_offset_days: toNullableInt(values.create_offset_days) ?? 0,
        due_offset_days: toNullableInt(values.due_offset_days) ?? 0,
      },
      jsonError: parsed.error,
    };
  }

  function validateTemplate(values: TemplateFormValues): string | null {
    const { payload, jsonError } = buildTemplatePayload(values);
    if (!String(payload.title ?? "").trim()) return "Название обязательно.";
    if (jsonError) return jsonError;
    return null;
  }

  async function submitTemplate(values: TemplateFormValues) {
    const { payload, jsonError } = buildTemplatePayload(values);

    if (!String(payload.title ?? "").trim()) {
      setDrawerError("Название обязательно.");
      return;
    }

    if (jsonError) {
      setDrawerError(jsonError);
      return;
    }

    setDrawerSaving(true);
    setDrawerError(null);

    try {
      if (drawerMode === "create") {
        const created = await apiFetchJson<RegularTaskItem>("/regular-tasks", {
          method: "POST",
          body: payload,
        });

        await loadTemplates();

        if (created?.regular_task_id) {
          setSelectedTemplateId(created.regular_task_id);
          setDrawerMode("view");
          await loadTemplateCard(created.regular_task_id);
        }
      } else if (drawerMode === "edit" && selectedTemplateId != null) {
        await apiFetchJson<RegularTaskItem>(`/regular-tasks/${selectedTemplateId}`, {
          method: "PATCH",
          body: payload,
        });

        await loadTemplates();
        await loadTemplateCard(selectedTemplateId);
        setDrawerMode("view");
      }
    } catch (err) {
      setDrawerError(errorText(err, "Не удалось сохранить шаблон."));
    } finally {
      setDrawerSaving(false);
    }
  }

  async function toggleTemplateActive(nextActive: boolean) {
    if (selectedTemplateId == null) return;

    setDrawerSaving(true);
    setDrawerError(null);

    try {
      const path = nextActive
        ? `/regular-tasks/${selectedTemplateId}/activate`
        : `/regular-tasks/${selectedTemplateId}/deactivate`;

      await apiFetchJson(path, { method: "POST" });
      await loadTemplates();
      await loadTemplateCard(selectedTemplateId);
    } catch (err) {
      setDrawerError(errorText(err, "Не удалось изменить статус шаблона."));
    } finally {
      setDrawerSaving(false);
    }
  }

  async function deleteTemplate(item: RegularTaskItem) {
    const label = item.title || `#${item.regular_task_id}`;
    const ok = window.confirm(`Удалить шаблон "${label}"?`);
    if (!ok) return;

    setDrawerSaving(true);
    setDrawerError(null);

    try {
      await apiFetchJson(`/regular-tasks/${item.regular_task_id}`, { method: "DELETE" });

      if (selectedTemplateId === item.regular_task_id) {
        setDrawerOpen(false);
        setSelectedTemplateId(null);
        setSelectedTemplate(null);
      }

      await loadTemplates();
    } catch (err) {
      setDrawerError(errorText(err, "Не удалось удалить шаблон."));
    } finally {
      setDrawerSaving(false);
    }
  }

  const drawerTitle =
    drawerMode === "create"
      ? "Создание шаблона"
      : drawerMode === "edit"
        ? "Редактирование шаблона"
        : currentTemplate
          ? currentTemplate.title
          : "Карточка шаблона";

  return (
    <div className="flex flex-col gap-5 text-zinc-100">
      <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 shadow-sm">
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_430px]">
          <div className="space-y-4">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-zinc-100">Регулярные задачи</h1>
              <p className="mt-2 text-base text-zinc-400">
                Управление шаблонами, историей запусков и ручным запуском генератора.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              {metricCard("Шаблонов", templates.length)}
              {metricCard("Активных", templatesActiveCount)}
              {metricCard("Запусков", runs.length)}
            </div>
          </div>

          <div className="rounded-2xl border border-zinc-800 bg-zinc-950/40 p-4">
            <div className="mb-4">
              <h2 className="text-base font-semibold text-zinc-100">Ручной запуск</h2>
              <p className="mt-1 text-sm text-zinc-400">
                Пробный или боевой запуск генератора регулярных задач.
              </p>
            </div>

            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-sm font-medium text-zinc-300">run_at_local_iso</label>
                <input
                  className="h-11 rounded-xl border border-zinc-700 bg-zinc-950/60 px-4 text-sm text-zinc-100 outline-none transition focus:border-zinc-500"
                  placeholder="2026-03-08T10:00:00"
                  value={runAtLocalIso}
                  onChange={(e) => setRunAtLocalIso(e.target.value)}
                />
              </div>

              <label className="flex items-center gap-2 rounded-xl border border-zinc-700 bg-zinc-950/60 px-4 py-3 text-sm text-zinc-200">
                <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
                dry_run
              </label>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={handleRunSubmit}
                  disabled={runSubmitting}
                  className="rounded-xl border border-zinc-700 bg-zinc-950/60 px-4 py-2.5 text-sm font-medium text-zinc-100 transition hover:bg-zinc-900 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {runSubmitting ? "Запуск..." : dryRun ? "Пробный запуск" : "Боевой запуск"}
                </button>

                <button
                  type="button"
                  onClick={handleRefreshAll}
                  className="rounded-xl border border-zinc-700 bg-zinc-950/60 px-4 py-2.5 text-sm font-medium text-zinc-100 transition hover:bg-zinc-900"
                >
                  Обновить
                </button>
              </div>
            </div>
          </div>
        </div>

        {(runSubmitError || lastRunResult) && (
          <div className="mt-4 rounded-2xl border border-zinc-800 bg-zinc-950/50 p-4 text-sm">
            {runSubmitError ? (
              <div className="text-red-300">{runSubmitError}</div>
            ) : lastRunResult ? (
              <div className="grid gap-3 sm:grid-cols-4">
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
      </section>

      <section className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-5 shadow-sm">
        <div className="mb-5 flex flex-col gap-3 border-b border-zinc-800 pb-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setActiveTab("templates")}
              className={[
                "rounded-xl border px-4 py-2.5 text-sm font-medium transition",
                activeTab === "templates"
                  ? "border-zinc-700 bg-zinc-950 text-zinc-100"
                  : "border-zinc-800 bg-zinc-900/30 text-zinc-400 hover:bg-zinc-900/50 hover:text-zinc-200",
              ].join(" ")}
            >
              Шаблоны · {filteredTemplates.length}
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("runs")}
              className={[
                "rounded-xl border px-4 py-2.5 text-sm font-medium transition",
                activeTab === "runs"
                  ? "border-zinc-700 bg-zinc-950 text-zinc-100"
                  : "border-zinc-800 bg-zinc-900/30 text-zinc-400 hover:bg-zinc-900/50 hover:text-zinc-200",
              ].join(" ")}
            >
              Запуски · {runs.length}
            </button>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="text-sm text-zinc-400">Группа отделений</div>
            <select
              className="min-w-[280px] rounded-xl border border-zinc-700 bg-zinc-950/60 px-4 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-zinc-500"
              value={orgGroup}
              onChange={(e) => setOrgGroup(e.target.value as OrgGroupFilter)}
            >
              {ORG_GROUP_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value} className="bg-zinc-950 text-zinc-100">
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {activeTab === "templates" ? (
          <section className="flex flex-col gap-4">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <h2 className="text-2xl font-semibold text-zinc-100">Шаблоны регулярных задач</h2>
                <p className="mt-1 text-sm text-zinc-400">
                  Всего: {templates.length} · Активных: {templatesActiveCount} · Группа: {selectedOrgGroupLabel}
                </p>
              </div>

              <div className="flex flex-col gap-2 md:flex-row">
                <input
                  className="w-full rounded-xl border border-zinc-700 bg-zinc-950/60 px-4 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-zinc-500 md:w-[320px]"
                  placeholder="Поиск по названию, расписанию, роли..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />

                <select
                  className="rounded-xl border border-zinc-700 bg-zinc-950/60 px-4 py-2.5 text-sm text-zinc-100 outline-none transition focus:border-zinc-500"
                  value={activeFilter}
                  onChange={(e) => setActiveFilter(e.target.value as "all" | "active" | "inactive")}
                >
                  <option value="all">Все</option>
                  <option value="active">Только активные</option>
                  <option value="inactive">Только неактивные</option>
                </select>

                <button
                  type="button"
                  onClick={openCreateTemplate}
                  className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-500"
                >
                  Создать
                </button>
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
                  <thead className="sticky top-0 bg-zinc-900 text-left">
                    <tr>
                      <th className="w-[72px] px-4 py-3 font-medium text-zinc-300">ID</th>
                      <th className="px-4 py-3 font-medium text-zinc-300">Отчёт</th>
                      <th className="w-[160px] px-4 py-3 font-medium text-zinc-300">Расписание</th>
                      <th className="w-[130px] px-4 py-3 font-medium text-zinc-300">Роль</th>
                      <th className="w-[120px] px-4 py-3 font-medium text-zinc-300">Статус</th>
                      <th className="w-[220px] px-4 py-3 font-medium text-zinc-300">Действия</th>
                    </tr>
                  </thead>

                  <tbody>
                    {filteredTemplates.map((item) => {
                      const selected = selectedTemplateId === item.regular_task_id && drawerOpen;
                      return (
                        <tr
                          key={item.regular_task_id}
                          className={[
                            "cursor-pointer border-t border-zinc-800 align-top transition",
                            selected ? "bg-zinc-800/60" : "hover:bg-zinc-900/50",
                          ].join(" ")}
                          onClick={() => openViewTemplate(item)}
                        >
                          <td className="px-4 py-3 text-zinc-200">{item.regular_task_id}</td>
                          <td className="px-4 py-3 text-zinc-100">
                            <div className="font-medium">{item.title}</div>
                            {item.description ? (
                              <div className="mt-1 line-clamp-2 text-xs text-zinc-400">{item.description}</div>
                            ) : null}
                          </td>
                          <td className="px-4 py-3 text-zinc-300">{scheduleLabel(item)}</td>
                          <td className="px-4 py-3 text-zinc-300">{item.executor_role_id ?? "—"}</td>
                          <td className="px-4 py-3">
                            <span
                              className={[
                                "inline-flex rounded-full px-2.5 py-1 text-xs font-medium",
                                item.is_active
                                  ? "bg-emerald-950/60 text-emerald-300"
                                  : "bg-zinc-800 text-zinc-300",
                              ].join(" ")}
                            >
                              {item.is_active ? "Активен" : "Неактивен"}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  openViewTemplate(item);
                                }}
                                className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-1.5 text-xs text-zinc-100 transition hover:bg-zinc-900/60"
                              >
                                Открыть
                              </button>

                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  openEditTemplate(item);
                                }}
                                className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-1.5 text-xs text-zinc-100 transition hover:bg-zinc-900/60"
                              >
                                Изменить
                              </button>

                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  void deleteTemplate(item);
                                }}
                                className="rounded-md border border-red-800 bg-transparent px-3 py-1.5 text-xs text-red-300 transition hover:bg-red-950/30"
                              >
                                Удалить
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}

                    {filteredTemplates.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-4 py-8 text-center text-zinc-500">
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
              <h2 className="text-2xl font-semibold text-zinc-100">История запусков</h2>
              <p className="mt-1 text-sm text-zinc-400">
                Последние записи по генератору регулярных задач · Группа: {selectedOrgGroupLabel}
              </p>
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
                      <th className="w-[90px] px-4 py-3 font-medium text-zinc-300">Запуск</th>
                      <th className="w-[210px] px-4 py-3 font-medium text-zinc-300">Старт</th>
                      <th className="w-[120px] px-4 py-3 font-medium text-zinc-300">Статус</th>
                      <th className="w-[110px] px-4 py-3 font-medium text-zinc-300">Создано</th>
                      <th className="w-[110px] px-4 py-3 font-medium text-zinc-300">Дедупл.</th>
                      <th className="w-[100px] px-4 py-3 font-medium text-zinc-300">Ошибки</th>
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
                          <td className="px-4 py-3 font-medium text-zinc-100">{run.run_id}</td>
                          <td className="px-4 py-3 text-zinc-300">{fmtDateTime(run.started_at)}</td>
                          <td className={`px-4 py-3 ${statTone(run.status)}`}>{run.status}</td>
                          <td className="px-4 py-3 text-zinc-300">{run.stats?.created ?? 0}</td>
                          <td className="px-4 py-3 text-zinc-300">{run.stats?.deduped ?? 0}</td>
                          <td className="px-4 py-3 text-zinc-300">{run.stats?.errors ?? 0}</td>
                        </tr>
                      );
                    })}

                    {runs.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-4 py-8 text-center text-zinc-500">
                          Нет запусков.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            <div className="rounded-2xl border border-zinc-800 bg-zinc-950/40 p-5">
              <div className="mb-4">
                <h3 className="text-lg font-semibold text-zinc-100">Детализация запуска</h3>
                <p className="mt-1 text-sm text-zinc-400">
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
                        <th className="w-[110px] px-4 py-3 font-medium text-zinc-300">Шаблон</th>
                        <th className="w-[100px] px-4 py-3 font-medium text-zinc-300">Период</th>
                        <th className="w-[140px] px-4 py-3 font-medium text-zinc-300">Исполнитель</th>
                        <th className="w-[110px] px-4 py-3 font-medium text-zinc-300">Актуален</th>
                        <th className="w-[100px] px-4 py-3 font-medium text-zinc-300">Создано</th>
                        <th className="w-[110px] px-4 py-3 font-medium text-zinc-300">Статус</th>
                        <th className="px-4 py-3 font-medium text-zinc-300">Ошибка</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runItems.map((item) => (
                        <tr key={item.item_id} className="border-t border-zinc-800 align-top hover:bg-zinc-900/50">
                          <td className="px-4 py-3 text-zinc-200">{item.regular_task_id}</td>
                          <td className="px-4 py-3 text-zinc-300">{item.period_id ?? "—"}</td>
                          <td className="px-4 py-3 text-zinc-300">{item.executor_role_id ?? "—"}</td>
                          <td className="px-4 py-3 text-zinc-300">{yesNo(item.is_due)}</td>
                          <td className="px-4 py-3 text-zinc-300">{item.created_tasks}</td>
                          <td className={`px-4 py-3 ${statTone(item.status)}`}>{item.status}</td>
                          <td className="px-4 py-3 text-xs text-red-300">{item.error ?? "—"}</td>
                        </tr>
                      ))}

                      {runItems.length === 0 && (
                        <tr>
                          <td colSpan={7} className="px-4 py-8 text-center text-zinc-500">
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
      </section>

      <TemplateDrawer
        open={drawerOpen}
        title={drawerTitle}
        subtitle={drawerMode === "create" ? "Шаблоны регулярных задач" : "Регулярные задачи"}
        onClose={closeDrawer}
      >
        {drawerMode === "view" ? (
          <div className="flex h-full flex-col bg-[#050816] text-zinc-100">
            <div className="flex-1 overflow-y-auto px-6 py-5">
              {drawerLoading && !currentTemplate ? (
                <div className="text-sm text-zinc-400">Загрузка...</div>
              ) : !currentTemplate ? (
                <div className="text-sm text-zinc-500">Шаблон не выбран.</div>
              ) : (
                <div className="space-y-5">
                  {!!drawerError && (
                    <div className="rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
                      {drawerError}
                    </div>
                  )}

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">ID</div>
                      <div className="mt-1 text-sm text-zinc-100">{currentTemplate.regular_task_id}</div>
                    </div>

                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">Активен</div>
                      <div className="mt-1 text-sm text-zinc-100">{currentTemplate.is_active ? "Да" : "Нет"}</div>
                    </div>

                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">Тип расписания</div>
                      <div className="mt-1 text-sm text-zinc-100">{currentTemplate.schedule_type ?? "—"}</div>
                    </div>

                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">ID роли исполнителя</div>
                      <div className="mt-1 text-sm text-zinc-100">{currentTemplate.executor_role_id ?? "—"}</div>
                    </div>

                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">Создать за N дней</div>
                      <div className="mt-1 text-sm text-zinc-100">{currentTemplate.create_offset_days ?? 0}</div>
                    </div>

                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">Срок +N дней</div>
                      <div className="mt-1 text-sm text-zinc-100">{currentTemplate.due_offset_days ?? 0}</div>
                    </div>

                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">Область назначения</div>
                      <div className="mt-1 text-sm text-zinc-100">{currentTemplate.assignment_scope ?? "—"}</div>
                    </div>

                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">Создал пользователь</div>
                      <div className="mt-1 text-sm text-zinc-100">{currentTemplate.created_by_user_id ?? "—"}</div>
                    </div>

                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">Обновлено</div>
                      <div className="mt-1 text-sm text-zinc-100">{fmtDateTime(currentTemplate.updated_at)}</div>
                    </div>
                  </div>

                  <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                    <div className="text-xs text-zinc-500">Описание</div>
                    <div className="mt-2 whitespace-pre-wrap text-sm text-zinc-100">
                      {currentTemplate.description ?? "—"}
                    </div>
                  </div>

                  <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                    <div className="text-xs text-zinc-500">schedule_params</div>
                    <pre className="mt-2 overflow-auto text-sm text-zinc-200">
                      {JSON.stringify(currentTemplate.schedule_params ?? {}, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>

            {currentTemplate ? (
              <div className="flex flex-wrap items-center justify-end gap-2 border-t border-zinc-800 px-6 py-4">
                <button
                  type="button"
                  onClick={() => setDrawerMode("edit")}
                  disabled={drawerSaving || drawerLoading}
                  className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60 disabled:opacity-60"
                >
                  Изменить
                </button>

                <button
                  type="button"
                  onClick={() => void toggleTemplateActive(true)}
                  disabled={drawerSaving || drawerLoading || currentTemplate.is_active === true}
                  className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60 disabled:opacity-60"
                >
                  Активировать
                </button>

                <button
                  type="button"
                  onClick={() => void toggleTemplateActive(false)}
                  disabled={drawerSaving || drawerLoading || currentTemplate.is_active === false}
                  className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60 disabled:opacity-60"
                >
                  Деактивировать
                </button>

                <button
                  type="button"
                  onClick={() => void deleteTemplate(currentTemplate)}
                  disabled={drawerSaving || drawerLoading}
                  className="rounded-lg border border-red-900/60 bg-red-950/20 px-4 py-2 text-sm text-red-200 transition hover:bg-red-950/40 disabled:opacity-60"
                >
                  Удалить
                </button>
              </div>
            ) : null}
          </div>
        ) : (
          <TemplateForm
            mode={drawerMode}
            initialValues={initialFormValues}
            saving={drawerSaving}
            error={drawerError}
            validate={validateTemplate}
            onCancel={closeDrawer}
            onSubmit={submitTemplate}
          />
        )}
      </TemplateDrawer>
    </div>
  );
}