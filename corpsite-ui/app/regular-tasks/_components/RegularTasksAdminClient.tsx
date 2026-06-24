// FILE: corpsite-ui/app/regular-tasks/_components/RegularTasksAdminClient.tsx
"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import OrgScopeFilter from "@/components/OrgScopeFilter";
import { ORG_GROUP_ID_PARAM, readOrgScopeFromSearchParams } from "@/lib/orgScope";
import { apiFetchJson } from "../../../lib/api";
import { runStatusLabel, scheduleTypeLabel, formatThrownError, translateRunIssueMessage, uiFieldLabel } from "@/lib/i18n";
import { canEditTemplate, listStatusFilterToApi } from "@/lib/regularTaskTemplatePolicy";
import { parseScheduleParamsText } from "@/lib/regularTaskScheduleParams";
import { validateTemplateFormValues } from "@/lib/regularTaskTemplateFormValidation";
import TemplateDrawer from "../../regular-tasks/_components/TemplateDrawer";
import TemplateForm, {
  TEMPLATE_FORM_ID,
  type TemplateFormExecutorRoleOption,
  type TemplateFormOwnerUnitOption,
  type TemplateFormValues,
} from "../../regular-tasks/_components/TemplateForm";
import TemplateViewPanel from "../../regular-tasks/_components/TemplateViewPanel";

type RegularTaskItem = {
  regular_task_id: number;
  code?: string | null;
  title: string;
  description?: string | null;
  periodicity?: string | null;
  schedule_type?: string | null;
  schedule_params?: Record<string, unknown> | null;
  executor_role_id?: number | null;
  executor_role_name?: string | null;
  executor_role_code?: string | null;
  assignment_scope?: string | null;
  create_offset_days?: number | null;
  due_offset_days?: number | null;
  owner_unit_id?: number | null;
  owner_unit_name?: string | null;
  is_active: boolean;
  created_at?: string | null;
  archived_at?: string | null;
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
  executor_role_name?: string | null;
  executor_role_code?: string | null;
  is_due: boolean;
  created_tasks: number;
  error?: string | null;
};

type RunResult = {
  run_id: number;
  dry_run: boolean;
  stats: RunStats;
};

type OrgUnitItem = {
  id?: number;
  unit_id?: number;
  name?: string;
  code?: string | null;
  is_active?: boolean;
};

type OrgUnitsListResponse = {
  items?: OrgUnitItem[];
};

type RoleDirectoryItem = {
  role_id?: number;
  name?: string | null;
  role_name?: string | null;
  code?: string | null;
  role_code?: string | null;
};

type RolesListResponse = {
  items?: RoleDirectoryItem[];
};

type MainTab = "templates" | "runs";
type DrawerMode = "create" | "view" | "edit";
type OwnerFilter = "all" | "ok" | "defect";

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
  if (s === "ok") return "text-emerald-800 dark:text-emerald-200";
  if (s === "partial") return "text-amber-900 dark:text-amber-200";
  if (s === "error") return "text-red-700 dark:text-red-300";
  if (s === "skip") return "text-zinc-700 dark:text-zinc-300";
  return "text-zinc-800 dark:text-zinc-200";
}

function scheduleTypeCodeOf(item: RegularTaskItem): string {
  return String(item.schedule_type ?? item.periodicity ?? "").trim();
}

function scheduleLabel(item: RegularTaskItem): string {
  const code = scheduleTypeCodeOf(item);
  return code ? scheduleTypeLabel(code) : "—";
}

function errorText(err: unknown, fallback: string): string {
  return formatThrownError(err, { fallback });
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
  return parseScheduleParamsText(text);
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

function hasOwnerUnitDefect(item: { owner_unit_id?: number | null }): boolean {
  const ownerId = item.owner_unit_id;
  if (ownerId == null) return true;

  const n = Number(ownerId);
  if (!Number.isFinite(n)) return true;
  if (n <= 0) return true;

  return false;
}

function matchesSearch(item: RegularTaskItem, q: string): boolean {
  const query = normalizeText(q);
  if (!query) return true;

  const haystack = normalizeText(
    [
      String(item.regular_task_id),
      item.title ?? "",
      item.schedule_type ?? "",
      item.assignment_scope ?? "",
      item.executor_role_name ?? "",
      item.executor_role_code ?? "",
      item.executor_role_id != null ? String(item.executor_role_id) : "",
      item.owner_unit_id != null ? String(item.owner_unit_id) : "",
      item.owner_unit_name ?? "",
    ].join(" "),
  );

  return haystack.includes(query);
}

function roleLabel(value: {
  executor_role_id?: number | null;
  executor_role_name?: string | null;
  executor_role_code?: string | null;
}): string {
  const name = String(value.executor_role_name ?? "").trim();
  if (name) return name;

  const code = String(value.executor_role_code ?? "").trim();
  if (code) return code;

  if (value.executor_role_id != null) return `#${value.executor_role_id}`;
  return "—";
}

function normalizeOrgUnits(data: OrgUnitsListResponse | OrgUnitItem[]): TemplateFormOwnerUnitOption[] {
  const rows = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];

  return rows
    .flatMap((x): TemplateFormOwnerUnitOption[] => {
      const unitId = Number(x.unit_id ?? x.id);
      const name = String(x.name ?? "").trim();
      const code = x.code ?? null;

      if (!Number.isFinite(unitId) || unitId <= 0 || !name) return [];
      return [{ unit_id: unitId, name, code }];
    })
    .sort((a, b) => a.name.localeCompare(b.name, "ru"));
}

function normalizeExecutorRoles(
  data: RolesListResponse | RoleDirectoryItem[],
): TemplateFormExecutorRoleOption[] {
  const rows = Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];

  return rows
    .flatMap((row): TemplateFormExecutorRoleOption[] => {
      const roleId = Number(row.role_id);
      if (!Number.isFinite(roleId) || roleId <= 0) return [];

      const name = String(row.role_name ?? row.name ?? "").trim() || null;
      const code = String(row.role_code ?? row.code ?? "").trim() || null;
      return [{ role_id: roleId, name, code }];
    })
    .sort((a, b) => {
      const left = String(a.name ?? a.code ?? `#${a.role_id}`);
      const right = String(b.name ?? b.code ?? `#${b.role_id}`);
      return left.localeCompare(right, "ru");
    });
}

export default function RegularTasksAdminClient() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const orgScope = readOrgScopeFromSearchParams(sp);
  const orgGroupId = orgScope.org_group_id;
  const orgUnitId = sp.get("org_unit_id") ?? "";
  const prevOrgUnitRef = React.useRef<string>(orgUnitId);
  const prevOrgGroupRef = React.useRef<number | undefined>(orgGroupId);

  const [activeTab, setActiveTab] = React.useState<MainTab>("templates");

  const [templates, setTemplates] = React.useState<RegularTaskItem[]>([]);
  const [templatesTotal, setTemplatesTotal] = React.useState(0);
  const [templatesLoading, setTemplatesLoading] = React.useState(false);
  const [templatesError, setTemplatesError] = React.useState<string | null>(null);

  const [ownerUnitOptions, setOwnerUnitOptions] = React.useState<TemplateFormOwnerUnitOption[]>([]);
  const [ownerUnitLoading, setOwnerUnitLoading] = React.useState(false);
  const [executorRoleOptions, setExecutorRoleOptions] = React.useState<TemplateFormExecutorRoleOption[]>([]);
  const [executorRoleLoading, setExecutorRoleLoading] = React.useState(false);

  const [selectedTemplateId, setSelectedTemplateId] = React.useState<number | null>(null);
  const [selectedTemplate, setSelectedTemplate] = React.useState<RegularTaskItem | null>(null);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerMode, setDrawerMode] = React.useState<DrawerMode>("create");
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
  const [activeFilter, setActiveFilter] = React.useState<"all" | "active" | "archived">("active");
  const [ownerFilter, setOwnerFilter] = React.useState<OwnerFilter>("all");
  const [scheduleFilter, setScheduleFilter] = React.useState<string>("all");
  const [runAtLocalIso, setRunAtLocalIso] = React.useState("");
  const [dryRun, setDryRun] = React.useState(true);
  const [runSubmitting, setRunSubmitting] = React.useState(false);
  const [runSubmitError, setRunSubmitError] = React.useState<string | null>(null);
  const [lastRunResult, setLastRunResult] = React.useState<RunResult | null>(null);
  const [formValidationError, setFormValidationError] = React.useState<string | null>(null);

  const loadTemplates = React.useCallback(async () => {
    setTemplatesLoading(true);
    setTemplatesError(null);

    try {
      const data = await apiFetchJson<RegularTasksListResponse>("/regular-tasks", {
        query: {
          status: listStatusFilterToApi(activeFilter),
          limit: 200,
          offset: 0,
          org_group_id: orgGroupId ?? undefined,
          org_unit_id: orgUnitId || undefined,
        },
      });

      const rows = normalizeTemplateList(data);
      const total = Array.isArray(data) ? rows.length : Number(data?.total ?? rows.length);

      setTemplates(rows);
      setTemplatesTotal(Number.isFinite(total) ? total : rows.length);

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
      setTemplatesTotal(0);
    } finally {
      setTemplatesLoading(false);
    }
  }, [orgGroupId, orgUnitId, selectedTemplateId, drawerOpen, drawerMode, activeFilter]);

  const loadOwnerUnits = React.useCallback(async () => {
    setOwnerUnitLoading(true);

    try {
      try {
        const data = await apiFetchJson<OrgUnitsListResponse>("/org-units", {
          query: { status: "active" },
        });
        setOwnerUnitOptions(normalizeOrgUnits(data));
      } catch {
        const data = await apiFetchJson<OrgUnitsListResponse>("/directory/org-units", {
          query: { status: "active" },
        });
        setOwnerUnitOptions(normalizeOrgUnits(data));
      }
    } catch {
      setOwnerUnitOptions([]);
    } finally {
      setOwnerUnitLoading(false);
    }
  }, []);

  const loadExecutorRoles = React.useCallback(async () => {
    setExecutorRoleLoading(true);

    try {
      const data = await apiFetchJson<RolesListResponse>("/directory/roles", {
        query: { is_active: true, limit: 200 },
      });
      setExecutorRoleOptions(normalizeExecutorRoles(data));
    } catch {
      setExecutorRoleOptions([]);
    } finally {
      setExecutorRoleLoading(false);
    }
  }, []);

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
          org_group_id: orgGroupId ?? undefined,
          org_unit_id: orgUnitId || undefined,
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
  }, [orgGroupId, orgUnitId, selectedRunId]);

  const loadRunItems = React.useCallback(
    async (runId: number) => {
      setRunItemsLoading(true);
      setRunItemsError(null);

      try {
        const data = await apiFetchJson<RunItem[]>(`/regular-task-runs/${runId}/items`, {
          query: {
            org_group_id: orgGroupId ?? undefined,
            org_unit_id: orgUnitId || undefined,
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
    [orgGroupId, orgUnitId],
  );

  React.useEffect(() => {
    void Promise.all([loadTemplates(), loadRuns(), loadOwnerUnits(), loadExecutorRoles()]);
  }, [loadTemplates, loadRuns, loadOwnerUnits, loadExecutorRoles]);

  React.useEffect(() => {
    if (prevOrgUnitRef.current !== orgUnitId) {
      prevOrgUnitRef.current = orgUnitId;

      setSelectedTemplateId(null);
      setSelectedTemplate(null);
      setDrawerOpen(false);
      setDrawerMode("view");
      setDrawerError(null);

      setSelectedRunId(null);
      setRunItems([]);
      setRunItemsError(null);
    }
  }, [orgUnitId]);

  React.useEffect(() => {
    if (prevOrgGroupRef.current !== orgGroupId) {
      prevOrgGroupRef.current = orgGroupId;

      setSelectedTemplateId(null);
      setSelectedTemplate(null);
      setDrawerOpen(false);
      setDrawerMode("view");
      setDrawerError(null);

      setSelectedRunId(null);
      setRunItems([]);
      setRunItemsError(null);
    }
  }, [orgGroupId]);

  React.useEffect(() => {
    if (selectedRunId == null) {
      setRunItems([]);
      return;
    }
    void loadRunItems(selectedRunId);
  }, [selectedRunId, loadRunItems]);

  const scheduleTypeOptions = React.useMemo(() => {
    const values = Array.from(
      new Set(
        templates
          .map((item) => String(item.schedule_type ?? item.periodicity ?? "").trim())
          .filter(Boolean),
      ),
    ).sort((a, b) => a.localeCompare(b, "ru"));

    return values;
  }, [templates]);

  const baseTemplates = React.useMemo(() => {
    return templates.filter((item) => {
      if (scheduleFilter !== "all" && scheduleTypeCodeOf(item) !== scheduleFilter) return false;
      return matchesSearch(item, query);
    });
  }, [templates, query, scheduleFilter]);

  const filteredTemplates = React.useMemo(() => {
    return baseTemplates.filter((item) => {
      const defect = hasOwnerUnitDefect(item);
      if (ownerFilter === "ok" && defect) return false;
      if (ownerFilter === "defect" && !defect) return false;
      return true;
    });
  }, [baseTemplates, ownerFilter]);

  const defectTemplatesTotal = React.useMemo(() => {
    return baseTemplates.reduce((acc, item) => acc + (hasOwnerUnitDefect(item) ? 1 : 0), 0);
  }, [baseTemplates]);

  const defectTemplatesVisible = React.useMemo(() => {
    return filteredTemplates.reduce((acc, item) => acc + (hasOwnerUnitDefect(item) ? 1 : 0), 0);
  }, [filteredTemplates]);

  const selectedTemplateFromList = React.useMemo(() => {
    if (selectedTemplateId == null) return null;
    return templates.find((x) => x.regular_task_id === selectedTemplateId) ?? null;
  }, [templates, selectedTemplateId]);

  const currentTemplate = selectedTemplate ?? selectedTemplateFromList ?? null;
  const currentTemplateHasOwnerDefect = currentTemplate ? hasOwnerUnitDefect(currentTemplate) : false;

  const initialFormValues = React.useMemo<TemplateFormValues>(() => {
    const x = currentTemplate ?? null;
    return {
      title: String(x?.title ?? ""),
      description: String(x?.description ?? ""),
      executor_role_id: x?.executor_role_id != null ? String(x.executor_role_id) : "",
      owner_unit_id: x?.owner_unit_id != null ? String(x.owner_unit_id) : "",
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
    currentTemplate?.owner_unit_id,
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
    setQuery("");
    setScheduleFilter("all");
    setActiveFilter("active");
    setOwnerFilter("all");
    setRunSubmitError(null);
    setLastRunResult(null);

    setSelectedTemplateId(null);
    setSelectedTemplate(null);
    setDrawerOpen(false);
    setDrawerMode("view");
    setDrawerError(null);

    const params = new URLSearchParams(sp.toString());
    const hadOrgUnitFilter = params.has("org_unit_id");
    const hadOrgGroupFilter = params.has(ORG_GROUP_ID_PARAM);
    if (hadOrgUnitFilter || hadOrgGroupFilter) {
      if (hadOrgUnitFilter) params.delete("org_unit_id");
      if (hadOrgGroupFilter) params.delete(ORG_GROUP_ID_PARAM);
      const next = params.toString();
      router.replace(next ? `${pathname}?${next}` : pathname);
      return;
    }

    await Promise.all([loadTemplates(), loadRuns(), loadOwnerUnits(), loadExecutorRoles()]);

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
    setFormValidationError(null);
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
    if (!canEditTemplate(item)) return;
    setSelectedTemplateId(item.regular_task_id);
    setSelectedTemplate(item);
    setDrawerMode("edit");
    setDrawerError(null);
    setFormValidationError(null);
    setDrawerOpen(true);
    void loadTemplateCard(item.regular_task_id);
  }

  function closeDrawer() {
    if (drawerSaving) return;
    setDrawerOpen(false);
    setDrawerMode("view");
    setDrawerError(null);
    setFormValidationError(null);
    setDrawerLoading(false);
  }

  function buildTemplatePayload(values: TemplateFormValues) {
    const parsed = parseJsonObject(values.schedule_params);

    return {
      payload: {
        title: String(values.title ?? "").trim(),
        description: String(values.description ?? "").trim() || null,
        executor_role_id: toNullableInt(values.executor_role_id),
        owner_unit_id: toNullableInt(values.owner_unit_id),
        schedule_type: String(values.schedule_type ?? "").trim() || null,
        schedule_params: parsed.value,
        create_offset_days: toNullableInt(values.create_offset_days) ?? 0,
        due_offset_days: toNullableInt(values.due_offset_days) ?? 0,
      },
      jsonError: parsed.error,
    };
  }

  function validateTemplate(values: TemplateFormValues): string | null {
    return validateTemplateFormValues(values);
  }

  const handleFormValidationChange = React.useCallback((error: string | null) => {
    setFormValidationError(error);
  }, []);

  async function submitTemplate(values: TemplateFormValues) {
    const validationError = validateTemplateFormValues(values);
    if (validationError) {
      setDrawerError(validationError);
      return;
    }

    const { payload, jsonError } = buildTemplatePayload(values);

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

  async function archiveTemplate(item: RegularTaskItem) {
    const label = item.title || `#${item.regular_task_id}`;
    const ok = window.confirm(`Архивировать шаблон "${label}"?`);
    if (!ok) return;

    setDrawerSaving(true);
    setDrawerError(null);

    try {
      await apiFetchJson(`/regular-tasks/${item.regular_task_id}/archive`, { method: "POST" });

      if (selectedTemplateId === item.regular_task_id) {
        setDrawerOpen(false);
        setSelectedTemplateId(null);
        setSelectedTemplate(null);
      }

      await loadTemplates();
    } catch (err) {
      setDrawerError(errorText(err, "Не удалось архивировать шаблон."));
    } finally {
      setDrawerSaving(false);
    }
  }

  async function copyTemplate(item: RegularTaskItem) {
    setDrawerSaving(true);
    setDrawerError(null);

    try {
      const copied = await apiFetchJson<RegularTaskItem>(`/regular-tasks/${item.regular_task_id}/copy`, {
        method: "POST",
      });

      await loadTemplates();

      if (copied?.regular_task_id) {
        setSelectedTemplateId(copied.regular_task_id);
        setSelectedTemplate(copied);
        setFormValidationError(null);
        setDrawerMode("edit");
        setDrawerOpen(true);
        await loadTemplateCard(copied.regular_task_id);
      }
    } catch (err) {
      setDrawerError(errorText(err, "Не удалось скопировать шаблон."));
    } finally {
      setDrawerSaving(false);
    }
  }

  const drawerTitle =
    drawerMode === "create"
      ? "Создание шаблона"
      : drawerMode === "edit"
        ? "Редактирование шаблона"
        : "Просмотр шаблона";

  const isTemplateFormMode = drawerMode === "create" || drawerMode === "edit";

  React.useEffect(() => {
    if (!isTemplateFormMode) {
      setFormValidationError(null);
    }
  }, [isTemplateFormMode]);

  return (
    <div className="notranslate flex flex-col gap-3 text-zinc-900 dark:text-zinc-50" lang="ru" translate="no">
      <section className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-3 shadow-sm">
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-2 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <h1 className="text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">Шаблоны регулярных задач</h1>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setActiveTab("templates")}
                className={[
                  "rounded-xl border px-4 py-2 text-sm font-medium transition",
                  activeTab === "templates"
                    ? "border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50"
                    : "border-zinc-200 dark:border-zinc-800 bg-zinc-100/30 dark:bg-zinc-900/30 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700/50 dark:hover:bg-zinc-800/50 hover:text-zinc-800 dark:hover:text-zinc-200",
                ].join(" ")}
              >
                Шаблоны
              </button>

              <button
                type="button"
                onClick={() => setActiveTab("runs")}
                className={[
                  "rounded-xl border px-4 py-2 text-sm font-medium transition",
                  activeTab === "runs"
                    ? "border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50"
                    : "border-zinc-200 dark:border-zinc-800 bg-zinc-100/30 dark:bg-zinc-900/30 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700/50 dark:hover:bg-zinc-800/50 hover:text-zinc-800 dark:hover:text-zinc-200",
                ].join(" ")}
              >
                Запуски
              </button>

              <OrgScopeFilter basePath="/regular-tasks" className="min-w-[240px]" />

              <button
                type="button"
                onClick={handleRefreshAll}
                className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-4 py-2 text-sm font-medium text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
              >
                Обновить
              </button>
            </div>
          </div>

          {activeTab === "templates" ? (
            <div className="flex flex-col gap-2">
              <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
                <div className="flex flex-1 flex-col gap-2 md:flex-row md:flex-wrap">
                  <input
                    className="w-full rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-500 md:w-[420px]"
                    placeholder="Поиск по названию, расписанию, ролям, владельцу..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />

                  <select
                    className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-500"
                    value={scheduleFilter}
                    onChange={(e) => setScheduleFilter(e.target.value)}
                  >
                    <option value="all">Периодичность: все</option>
                    {scheduleTypeOptions.map((value) => (
                      <option key={value} value={value}>
                        {scheduleTypeLabel(value)}
                      </option>
                    ))}
                  </select>

                  <select
                    className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-500"
                    value={activeFilter}
                    onChange={(e) => setActiveFilter(e.target.value as "all" | "active" | "archived")}
                  >
                    <option value="active">Активные</option>
                    <option value="archived">Архивные</option>
                    <option value="all">Все</option>
                  </select>

                  <select
                    className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-500"
                    value={ownerFilter}
                    onChange={(e) => setOwnerFilter(e.target.value as OwnerFilter)}
                  >
                    <option value="all">Все владельцы_единиц</option>
                    <option value="ok">Только с отделением</option>
                    <option value="defect">Только дефектные</option>
                  </select>
                </div>

                <button
                  type="button"
                  onClick={openCreateTemplate}
                  className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500"
                >
                  Создать
                </button>
              </div>

              <div className="flex flex-wrap gap-2 text-xs text-zinc-600 dark:text-zinc-400">
                <span className="rounded-full border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2.5 py-1">
                  Всего: {templatesTotal}
                </span>
                <span className="rounded-full border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2.5 py-1">
                  Показано: {filteredTemplates.length}
                </span>
                <span className="rounded-full border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 px-2.5 py-1 text-amber-900 dark:text-amber-200">
                  Дефектных отделений: {defectTemplatesTotal}
                </span>
                <span className="rounded-full border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2.5 py-1">
                  В текущем фильтре: {defectTemplatesVisible}
                </span>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-2 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex flex-1 flex-col gap-2 md:flex-row">
                <input
                  className="h-10 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-500 md:w-[260px]"
                  placeholder="2026-03-08T10:00:00"
                  value={runAtLocalIso}
                  onChange={(e) => setRunAtLocalIso(e.target.value)}
                />

                <label className="flex items-center gap-2 rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-3 py-2 text-sm text-zinc-800 dark:text-zinc-200">
                  <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
                  {uiFieldLabel("dry_run")}
                </label>
              </div>

              <button
                type="button"
                onClick={handleRunSubmit}
                disabled={runSubmitting}
                className="rounded-xl border border-zinc-300 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/60 px-4 py-2 text-sm font-medium text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {runSubmitting ? "Запуск..." : dryRun ? "Пробный запуск" : "Боевой запуск"}
              </button>
            </div>
          )}

          {(runSubmitError || lastRunResult) && (
            <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white/50 dark:bg-zinc-900/50 px-4 py-3 text-sm">
              {runSubmitError ? (
                <div className="text-red-700 dark:text-red-300">{runSubmitError}</div>
              ) : lastRunResult ? (
                <div className="flex flex-wrap gap-x-5 gap-y-1 text-zinc-700 dark:text-zinc-300">
                  <div>
                    <span className="font-medium text-zinc-800 dark:text-zinc-200">{uiFieldLabel("run_id")}:</span>{" "}
                    {lastRunResult.run_id}
                  </div>
                  <div>
                    <span className="font-medium text-zinc-800 dark:text-zinc-200">{uiFieldLabel("templates_due")}:</span>{" "}
                    {lastRunResult.stats?.templates_due ?? 0}
                  </div>
                  <div>
                    <span className="font-medium text-zinc-800 dark:text-zinc-200">{uiFieldLabel("created")}:</span>{" "}
                    {lastRunResult.stats?.created ?? 0}
                  </div>
                  <div>
                    <span className="font-medium text-zinc-800 dark:text-zinc-200">{uiFieldLabel("errors")}:</span>{" "}
                    {lastRunResult.stats?.errors ?? 0}
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>
      </section>

      {activeTab === "templates" ? (
        <section className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 shadow-sm">
          {templatesLoading ? (
            <div className="p-5 text-sm text-zinc-600 dark:text-zinc-400">Загрузка шаблонов...</div>
          ) : templatesError ? (
            <div className="m-3 rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 p-4 text-sm text-red-700 dark:text-red-300">
              {templatesError}
            </div>
          ) : (
            <div className="overflow-auto rounded-2xl">
              <table className="min-w-full table-fixed text-sm" lang="ru" translate="no">
                <thead className="sticky top-0 bg-zinc-100 dark:bg-zinc-900 text-left">
                  <tr>
                    <th className="w-[52px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Ид</th>
                    <th className="px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Шаблон</th>
                    <th className="w-[150px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Периодичность</th>
                    <th className="w-[190px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Исполнитель</th>
                    <th className="w-[210px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Подразделение</th>
                    <th className="w-[150px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Создан</th>
                    <th className="w-[150px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Архивирован</th>
                    <th className="w-[240px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Действия</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredTemplates.map((item) => {
                    const selected = selectedTemplateId === item.regular_task_id && drawerOpen;
                    const ownerDefect = hasOwnerUnitDefect(item);

                    return (
                      <tr
                        key={item.regular_task_id}
                        className={[
                          "cursor-pointer border-t border-zinc-200 dark:border-zinc-800 align-top transition",
                          selected
                            ? "bg-zinc-200/60 dark:bg-zinc-800/60"
                            : ownerDefect
                              ? "bg-amber-50 dark:bg-amber-950/30 hover:bg-amber-50 dark:bg-amber-950/30"
                              : "hover:bg-zinc-200 dark:hover:bg-zinc-700/50 dark:hover:bg-zinc-800/50",
                        ].join(" ")}
                        onClick={() => openViewTemplate(item)}
                      >
                        <td className="px-3 py-2 text-zinc-800 dark:text-zinc-200">{item.regular_task_id}</td>

                        <td className="px-3 py-2 text-zinc-900 dark:text-zinc-50">
                          <div className="font-medium">{item.title}</div>
                        </td>

                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{scheduleLabel(item)}</td>

                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{roleLabel(item)}</td>

                        <td className="px-3 py-2">
                          <div className="flex flex-col gap-1">
                            <div className="text-zinc-900 dark:text-zinc-50">{item.owner_unit_name?.trim() || "—"}</div>
                            <div className="text-xs text-zinc-600 dark:text-zinc-400">
                              {uiFieldLabel("owner_unit_id")}: {item.owner_unit_id ?? "—"}
                            </div>
                            {ownerDefect ? (
                              <span className="inline-flex w-fit rounded-full border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 px-2 py-0.5 text-[11px] font-medium text-amber-900 dark:text-amber-200">
                                Дефект
                              </span>
                            ) : null}
                          </div>
                        </td>

                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{fmtDateTime(item.created_at)}</td>

                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{fmtDateTime(item.archived_at)}</td>

                        <td className="px-3 py-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                openViewTemplate(item);
                              }}
                              className="rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2.5 py-1 text-xs text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
                            >
                              Открыть
                            </button>

                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                void copyTemplate(item);
                              }}
                              disabled={drawerSaving}
                              className="rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2.5 py-1 text-xs text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
                            >
                              Копировать
                            </button>

                            {canEditTemplate(item) ? (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  openEditTemplate(item);
                                }}
                                className="rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2.5 py-1 text-xs text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
                              >
                                Редактировать
                              </button>
                            ) : null}

                            {canEditTemplate(item) ? (
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  void archiveTemplate(item);
                                }}
                                disabled={drawerSaving}
                                className="rounded-md border border-amber-300 dark:border-amber-800 bg-transparent px-2.5 py-1 text-xs text-amber-900 dark:text-amber-200 transition hover:bg-amber-50 dark:hover:bg-amber-950/35 disabled:opacity-60"
                              >
                                Архивировать
                              </button>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })}

                  {filteredTemplates.length === 0 && (
                    <tr>
                      <td colSpan={8} className="px-4 py-8 text-center text-zinc-600 dark:text-zinc-400">
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
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(340px,420px)]">
          <section className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 shadow-sm">
            {runsLoading ? (
              <div className="p-5 text-sm text-zinc-600 dark:text-zinc-400">Загрузка истории запусков...</div>
            ) : runsError ? (
              <div className="m-3 rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 p-4 text-sm text-red-700 dark:text-red-300">
                {runsError}
              </div>
            ) : (
              <div className="overflow-auto rounded-2xl">
                <table className="min-w-full table-fixed text-sm">
                  <thead className="bg-zinc-100 dark:bg-zinc-900 text-left">
                    <tr>
                      <th className="w-[90px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Запуск</th>
                      <th className="w-[210px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Старт</th>
                      <th className="w-[110px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Статус</th>
                      <th className="w-[90px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Создано</th>
                      <th className="w-[90px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Дедупл.</th>
                      <th className="w-[90px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Ошибки</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => {
                      const selected = selectedRunId === run.run_id;
                      return (
                        <tr
                          key={run.run_id}
                          className={[
                            "cursor-pointer border-t border-zinc-200 dark:border-zinc-800",
                            selected ? "bg-zinc-200/80 dark:bg-zinc-800/80" : "hover:bg-zinc-200 dark:hover:bg-zinc-700/50 dark:hover:bg-zinc-800/50",
                          ].join(" ")}
                          onClick={() => setSelectedRunId(run.run_id)}
                        >
                          <td className="px-3 py-2 font-medium text-zinc-900 dark:text-zinc-50">{run.run_id}</td>
                          <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{fmtDateTime(run.started_at)}</td>
                          <td className={`px-3 py-2 ${statTone(run.status)}`}>{runStatusLabel(run.status)}</td>
                          <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{run.stats?.created ?? 0}</td>
                          <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{run.stats?.deduped ?? 0}</td>
                          <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{run.stats?.errors ?? 0}</td>
                        </tr>
                      );
                    })}

                    {runs.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-4 py-8 text-center text-zinc-600 dark:text-zinc-400">
                          Нет запусков.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-3 shadow-sm">
            <div className="mb-3">
              <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">Детализация запуска</h3>
              <p className="mt-0.5 text-sm text-zinc-600 dark:text-zinc-400">
                {selectedRunId != null ? `${uiFieldLabel("run_id")} = ${selectedRunId}` : "Запуск не выбран"}
              </p>
            </div>

            {selectedRunId == null ? (
              <div className="rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700 p-5 text-sm text-zinc-600 dark:text-zinc-400">
                Выбери запуск в таблице слева.
              </div>
            ) : runItemsLoading ? (
              <div className="rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700 p-5 text-sm text-zinc-600 dark:text-zinc-400">
                Загрузка деталей...
              </div>
            ) : runItemsError ? (
              <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 p-4 text-sm text-red-700 dark:text-red-300">
                {runItemsError}
              </div>
            ) : (
              <div className="overflow-auto rounded-2xl border border-zinc-200 dark:border-zinc-800">
                <table className="min-w-full table-fixed text-sm">
                  <thead className="bg-zinc-100 dark:bg-zinc-900 text-left">
                    <tr>
                      <th className="w-[90px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Шаблон</th>
                      <th className="w-[90px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Период</th>
                      <th className="w-[170px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Исполнитель</th>
                      <th className="w-[80px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">{uiFieldLabel("due")}</th>
                      <th className="w-[80px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Создано</th>
                      <th className="w-[90px] px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Статус</th>
                      <th className="px-3 py-2 font-medium text-zinc-700 dark:text-zinc-300">Ошибка</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runItems.map((item) => (
                      <tr key={item.item_id} className="border-t border-zinc-200 dark:border-zinc-800 align-top hover:bg-zinc-200 dark:hover:bg-zinc-700/50 dark:hover:bg-zinc-800/50">
                        <td className="px-3 py-2 text-zinc-800 dark:text-zinc-200">{item.regular_task_id}</td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{item.period_id ?? "—"}</td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{roleLabel(item)}</td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{yesNo(item.is_due)}</td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">{item.created_tasks}</td>
                        <td className={`px-3 py-2 ${statTone(item.status)}`}>{runStatusLabel(item.status)}</td>
                        <td className="px-3 py-2 text-xs text-red-700 dark:text-red-300">{translateRunIssueMessage(item.error)}</td>
                      </tr>
                    ))}

                    {runItems.length === 0 && (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-zinc-600 dark:text-zinc-400">
                          Нет элементов запуска.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}

      <TemplateDrawer
        open={drawerOpen}
        title={drawerTitle}
        subtitle="Шаблоны регулярных задач"
        onClose={closeDrawer}
        headerActions={
          isTemplateFormMode ? (
            <div className="flex flex-col items-end gap-1.5">
              {formValidationError ? (
                <p
                  className="max-w-sm text-right text-xs leading-snug text-red-700 dark:text-red-300"
                  role="alert"
                >
                  {formValidationError}
                </p>
              ) : null}
              <button
                type="submit"
                form={TEMPLATE_FORM_ID}
                disabled={drawerSaving || !!formValidationError}
                title={formValidationError ?? undefined}
                aria-describedby={formValidationError ? "template-form-validation-error" : undefined}
                className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {drawerSaving ? "Сохранение..." : drawerMode === "create" ? "Создать" : "Сохранить"}
              </button>
            </div>
          ) : null
        }
      >
        {drawerMode === "view" ? (
          drawerLoading && !currentTemplate ? (
            <div className="px-6 py-5 text-sm text-zinc-600 dark:text-zinc-400">Загрузка...</div>
          ) : !currentTemplate ? (
            <div className="px-6 py-5 text-sm text-zinc-600 dark:text-zinc-400">Шаблон не выбран.</div>
          ) : (
            <TemplateViewPanel
              template={currentTemplate}
              error={drawerError}
              hasOwnerDefect={currentTemplateHasOwnerDefect}
              roleLabel={roleLabel(currentTemplate)}
              formatDateTime={fmtDateTime}
              footer={
                <>
                  {canEditTemplate(currentTemplate) ? (
                    <button
                      type="button"
                      onClick={() => setDrawerMode("edit")}
                      disabled={drawerSaving || drawerLoading}
                      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-1.5 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
                    >
                      Редактировать
                    </button>
                  ) : null}

                  <button
                    type="button"
                    onClick={() => void copyTemplate(currentTemplate)}
                    disabled={drawerSaving || drawerLoading}
                    className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-1.5 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
                  >
                    Копировать
                  </button>

                  {canEditTemplate(currentTemplate) ? (
                    <button
                      type="button"
                      onClick={() => void archiveTemplate(currentTemplate)}
                      disabled={drawerSaving || drawerLoading}
                      className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 px-4 py-1.5 text-sm text-amber-900 dark:text-amber-200 transition hover:bg-amber-100 dark:hover:bg-amber-950/50 disabled:opacity-60"
                    >
                      Архивировать
                    </button>
                  ) : null}

                  {!canEditTemplate(currentTemplate) ? (
                    <button
                      type="button"
                      onClick={() => void toggleTemplateActive(true)}
                      disabled={drawerSaving || drawerLoading || currentTemplate.is_active === true}
                      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-1.5 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
                    >
                      Восстановить
                    </button>
                  ) : null}
                </>
              }
            />
          )
        ) : (
          <TemplateForm
            mode={drawerMode}
            initialValues={initialFormValues}
            saving={drawerSaving}
            error={drawerError}
            validate={validateTemplate}
            onFormValidationChange={handleFormValidationChange}
            onSubmit={submitTemplate}
            ownerUnitOptions={ownerUnitOptions}
            ownerUnitLoading={ownerUnitLoading}
            executorRoleOptions={executorRoleOptions}
            executorRoleLoading={executorRoleLoading}
          />
        )}
      </TemplateDrawer>
    </div>
  );
}