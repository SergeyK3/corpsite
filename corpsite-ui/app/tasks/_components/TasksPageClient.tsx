// FILE: corpsite-ui/app/tasks/_components/TasksPageClient.tsx
"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import TaskOrgFiltersBar from "@/components/TaskOrgFiltersBar";
import { apiAuthMe, apiFetchJson, apiGetTask, apiPostTaskAction } from "@/lib/api";
import { isAuthed, logout } from "@/lib/auth";
import { readOrgScopeFromSearchParams } from "@/lib/orgScope";
import { taskStatusLabel } from "@/lib/i18n";
import { parseTaskIdFromSearchParams, resolveTaskDrawerCloseTarget } from "@/lib/taskNav";
import { canEditTask, editButtonTitle, isTaskRowEditable } from "@/lib/taskEditPolicy";
import { taskPeriodicityLabel } from "@/lib/taskPeriodicity";
import { resolveTaskReportLink } from "@/lib/taskReportLink";
import {
  getTaskDisplayColor,
  taskDisplayColorDeadlineClass,
  taskDisplayColorTitleClass,
} from "@/lib/taskDisplayColor";
import {
  canSeeTeamTasks as userCanSeeTeamTasks,
  defaultTaskScope,
  isTaskSystemAdmin,
} from "@/lib/taskScopePolicy";
import {
  readTaskOrgFiltersFromSearchParams,
  shouldShowTaskOrgFilters,
} from "@/lib/taskOrgFilters";
import type { MeInfo } from "@/lib/types";

import CreateManualTaskModal, { type ManualTaskRoleOption } from "./CreateManualTaskModal";
import TaskDetailPanel from "./TaskDetailPanel";
import TaskDrawer from "./TaskDrawer";
import TaskEditForm, { type TaskEditValues } from "./TaskEditForm";

const LIST_LIMIT = 50;

type AllowedAction = "report" | "approve" | "reject" | "archive";
type TaskAction = AllowedAction;
type StatusTab = "active" | "done" | "rejected";
type DrawerMode = "create" | "view" | "edit";
type TaskKindFilter = "all" | "adhoc" | "regular" | "other";
type TaskScope = "mine" | "team";

type CurrentPeriodDto = {
  period_id?: number;
  id?: number;
  name?: string;
  date_from?: string;
  date_to?: string;
};

type ManualRolesResponse = {
  can_create_manual_task?: boolean;
  items?: ManualTaskRoleOption[];
};

type LoadItemsOptions = {
  offset?: number;
  statusTab?: StatusTab;
  taskScope?: TaskScope;
  orgGroupId?: number;
  orgUnitId?: string;
  positionId?: number;
  search?: string;
  taskKind?: TaskKindFilter;
};

function normalizeMsg(msg: string): string {
  const s = String(msg || "").trim();
  return s || "Ошибка запроса";
}

function isUnauthorized(e: any): boolean {
  return Number(e?.status ?? 0) === 401;
}

function normalizeList<T>(body: any): T[] {
  if (Array.isArray(body)) return body as T[];
  if (body?.items && Array.isArray(body.items)) return body.items as T[];
  return [];
}

function extractTotal(body: any, items: any[]): number {
  if (!Array.isArray(body) && typeof body?.total === "number") return body.total;
  return items.length;
}

function taskIdOf(t: any): number {
  return Number(t?.task_id ?? t?.id ?? 0);
}

function taskTitleOf(t: any): string {
  const id = taskIdOf(t);
  const title = String(t?.title ?? "").trim();
  return title || (id > 0 ? `Задача №${id}` : "Задача");
}

function statusTextOf(t: any): string {
  const sRu = String(t?.status_name_ru ?? "").trim();
  if (sRu) return sRu;

  const sCode = String(t?.status_code ?? "").trim();
  if (sCode) return taskStatusLabel(sCode);

  const sLegacy = String(t?.status ?? "").trim();
  if (sLegacy) return taskStatusLabel(sLegacy);

  const sid = t?.status_id;
  if (sid != null) return `Статус №${sid}`;

  return "—";
}

function allowedActionsOf(t: any): AllowedAction[] {
  const raw = t?.allowed_actions;
  const all: AllowedAction[] = ["report", "approve", "reject", "archive"];

  if (Array.isArray(raw)) {
    return raw
      .map((x) => String(x ?? "").trim().toLowerCase())
      .filter((x): x is AllowedAction => all.includes(x as AllowedAction));
  }

  if (raw && typeof raw === "object") {
    return all.filter((key) => Boolean(raw[key]));
  }

  return [];
}

function formatDeadline(t: any): string {
  const raw =
    t?.due_at ??
    t?.due_date ??
    t?.deadline ??
    t?.deadline_at ??
    t?.deadline_date ??
    t?.due ??
    null;

  if (!raw) return "—";
  const s = String(raw).trim();
  if (!s) return "—";

  if (/^\d{2}\.\d{2}\.\d{4}/.test(s)) return s;

  const d = new Date(s);
  if (!Number.isFinite(d.getTime())) return s;

  try {
    return d.toLocaleDateString("ru-RU");
  } catch {
    return s;
  }
}

function toDateInputValue(raw: any): string {
  if (!raw) return "";
  const s = String(raw).trim();
  if (!s) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;

  const d = new Date(s);
  if (!Number.isFinite(d.getTime())) return "";

  try {
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  } catch {
    return "";
  }
}

function tabRu(v: StatusTab): string {
  if (v === "done") return "Отработано";
  if (v === "rejected") return "Отклонено";
  return "В работе";
}

function scopeRu(v: TaskScope): string {
  return v === "team" ? "Все задачи" : "Мои задачи";
}

function currentPeriodIdOf(body: any): number {
  const raw = body?.period_id ?? body?.id ?? 0;
  const n = Number(raw);
  if (Number.isFinite(n) && n > 0) return n;
  return 3;
}

function normalizeManualRoleOptions(body: any): ManualTaskRoleOption[] {
  const items = Array.isArray(body?.items) ? body.items : [];
  return items
    .map((x: any) => ({
      role_id: Number(x?.role_id ?? 0),
      role_code: x?.role_code ?? null,
      role_name: x?.role_name ?? null,
      role_name_ru: x?.role_name_ru ?? null,
    }))
    .filter((x: ManualTaskRoleOption) => Number.isFinite(x.role_id) && x.role_id > 0);
}

function normalizeTaskKind(value: any): string {
  const s = String(value ?? "").trim().toLowerCase();
  if (s === "adhoc" || s === "regular") return s;
  return s ? "other" : "";
}

function executorRoleLabelOf(src: any): string {
  const roleRu = String(
    src?.executor_role_name_ru ??
      src?.role_name_ru ??
      src?.target_role_name_ru ??
      src?.executor_role_ru ??
      "",
  ).trim();
  if (roleRu) return roleRu;

  const roleName = String(
    src?.executor_role_name ??
      src?.role_name ??
      src?.target_role_name ??
      src?.executor_role ??
      "",
  ).trim();
  if (roleName) return roleName;

  const roleCode = String(
    src?.executor_role_code ??
      src?.role_code ??
      src?.target_role_code ??
      "",
  ).trim();
  if (roleCode) return roleCode;

  const roleId = Number(src?.executor_role_id ?? src?.role_id ?? 0);
  if (Number.isFinite(roleId) && roleId > 0) return `Роль #${roleId}`;

  const person = String(src?.executor_name ?? "").trim();
  return person || "—";
}

const TASK_KIND_OPTIONS: Array<{ value: TaskKindFilter; label: string }> = [
  { value: "all", label: "Все типы" },
  { value: "adhoc", label: "Разовые" },
  { value: "regular", label: "Регулярные" },
  { value: "other", label: "Прочие" },
];

export default function TasksPageClient() {
  const router = useRouter();
  const sp = useSearchParams();
  const detailsRequestRef = React.useRef(0);
  const listRequestSeqRef = React.useRef(0);

  const [ready, setReady] = React.useState(false);
  const [me, setMe] = React.useState<MeInfo | null>(null);

  const [offset, setOffset] = React.useState(0);
  const [tab, setTab] = React.useState<StatusTab>("active");
  const [taskScope, setTaskScope] = React.useState<TaskScope>("mine");
  const [search, setSearch] = React.useState("");
  const [searchQuery, setSearchQuery] = React.useState("");
  const [taskKind, setTaskKind] = React.useState<TaskKindFilter>("all");

  const [items, setItems] = React.useState<any[]>([]);
  const [total, setTotal] = React.useState(0);
  const [listLoading, setListLoading] = React.useState(false);
  const [pageError, setPageError] = React.useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerMode, setDrawerMode] = React.useState<DrawerMode>("create");
  const [selectedId, setSelectedId] = React.useState<number | null>(null);
  const [selectedItem, setSelectedItem] = React.useState<any | null>(null);
  const [drawerLoading, setDrawerLoading] = React.useState(false);
  const [drawerError, setDrawerError] = React.useState<string | null>(null);
  const [saving, setSaving] = React.useState(false);

  const [reportLink, setReportLink] = React.useState("");
  const [reason, setReason] = React.useState("");
  const [uiNotice, setUiNotice] = React.useState("");

  const [currentPeriodId, setCurrentPeriodId] = React.useState<number>(3);
  const [currentPeriodName, setCurrentPeriodName] = React.useState("");

  const [manualRoleOptions, setManualRoleOptions] = React.useState<ManualTaskRoleOption[]>([]);
  const [canCreateManualTask, setCanCreateManualTask] = React.useState(false);
  const [manualRolesLoading, setManualRolesLoading] = React.useState(false);

  const orgScope = readOrgScopeFromSearchParams(sp);
  const taskOrgFilters = React.useMemo(() => readTaskOrgFiltersFromSearchParams(sp), [sp]);
  const orgGroupId = orgScope.org_group_id;
  const orgUnitId = sp.get("org_unit_id") ?? "";
  const positionId = taskOrgFilters.position_id;
  const deepLinkTaskId = React.useMemo(() => parseTaskIdFromSearchParams(sp), [sp]);
  const prevOrgUnitRef = React.useRef<string>(orgUnitId);
  const prevOrgGroupRef = React.useRef<number | undefined>(orgGroupId);

  const isSystemAdmin = React.useMemo(() => isTaskSystemAdmin(me), [me]);
  const canSeeTeamTasks = React.useMemo(() => userCanSeeTeamTasks(me), [me]);

  const readOnlyTeamMode = taskScope === "team" && !isSystemAdmin;
  const showTaskOrgFilters = shouldShowTaskOrgFilters({
    isSystemAdmin,
    taskScope,
  });
  const showExecutorColumn = taskScope === "team";
  const showDeleteButtons = isSystemAdmin;
  const actionsColWidth = showDeleteButtons ? "w-[170px]" : "w-[138px]";

  const displayItems = React.useMemo(() => {
    if (taskKind !== "other") return items;
    return items.filter((item) => normalizeTaskKind(item?.task_kind) === "other");
  }, [items, taskKind]);

  const displayTotal = taskKind === "other" ? displayItems.length : total;

  const resetDrawerState = React.useCallback(() => {
    detailsRequestRef.current += 1;
    setDrawerOpen(false);
    setDrawerMode("view");
    setSelectedId(null);
    setSelectedItem(null);
    setDrawerError(null);
    setDrawerLoading(false);
    setSaving(false);
    setUiNotice("");
    setReason("");
    setReportLink("");
  }, []);

  const redirectToLogin = React.useCallback(() => {
    logout();
    router.replace("/login");
  }, [router]);

  const closeDrawer = React.useCallback(() => {
    if (saving) return;
    resetDrawerState();
    router.replace(resolveTaskDrawerCloseTarget(new URLSearchParams(sp.toString())));
  }, [saving, resetDrawerState, router, sp]);

  const loadCurrentPeriod = React.useCallback(async (): Promise<number> => {
    try {
      const body = await apiFetchJson<CurrentPeriodDto>("/periods/current");
      const pid = currentPeriodIdOf(body);
      setCurrentPeriodId(pid);
      setCurrentPeriodName(String(body?.name ?? "").trim());
      return pid;
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return 0;
      }
      setCurrentPeriodId(3);
      setCurrentPeriodName("");
      return 3;
    }
  }, [redirectToLogin]);

  const loadManualRoleOptions = React.useCallback(
    async (periodId: number) => {
      if (!periodId || periodId <= 0) {
        setManualRoleOptions([]);
        setCanCreateManualTask(false);
        return;
      }

      setManualRolesLoading(true);

      try {
        const body = await apiFetchJson<ManualRolesResponse>("/tasks/manual/available-roles", {
          query: { period_id: periodId },
        });

        const normalized = normalizeManualRoleOptions(body);
        const canCreate = Boolean(body?.can_create_manual_task) && normalized.length > 0;

        setManualRoleOptions(normalized);
        setCanCreateManualTask(canCreate);
      } catch (e: any) {
        if (isUnauthorized(e)) {
          redirectToLogin();
          return;
        }
        setManualRoleOptions([]);
        setCanCreateManualTask(false);
      } finally {
        setManualRolesLoading(false);
      }
    },
    [redirectToLogin],
  );

  const loadItems = React.useCallback(
    async (options?: LoadItemsOptions) => {
      const seq = ++listRequestSeqRef.current;
      const requestedScope: TaskScope = options?.taskScope ?? taskScope;
      setListLoading(true);
      setPageError(null);

      try {
        const qOffset = typeof options?.offset === "number" ? options.offset : offset;
        const qStatusTab = options?.statusTab ?? tab;
        const qOrgGroupId = typeof options?.orgGroupId === "number" ? options.orgGroupId : orgGroupId;
        const qOrgUnitId = typeof options?.orgUnitId === "string" ? options.orgUnitId : orgUnitId;
        const qPositionId = typeof options?.positionId === "number" ? options.positionId : positionId;
        const qSearch = typeof options?.search === "string" ? options.search : searchQuery;
        const qTaskKind = options?.taskKind ?? taskKind;
        const backendTaskKind =
          qTaskKind === "regular" || qTaskKind === "adhoc" ? qTaskKind : undefined;

        const body = await apiFetchJson<any>("/tasks", {
          query: {
            scope: requestedScope,
            limit: LIST_LIMIT,
            offset: qOffset,
            status_filter: qStatusTab,
            ...(requestedScope === "team" && isSystemAdmin
              ? {
                  org_group_id: qOrgGroupId ?? undefined,
                  org_unit_id: qOrgUnitId || undefined,
                  position_id: qPositionId ?? undefined,
                }
              : {}),
            search: qSearch || undefined,
            task_kind: backendTaskKind,
          } as any,
        });

        if (seq !== listRequestSeqRef.current) return;

        const normalized = normalizeList<any>(body);
        setItems(normalized);
        setTotal(extractTotal(body, normalized));

        if (selectedId && !normalized.some((x: any) => taskIdOf(x) === selectedId) && drawerMode !== "create") {
          resetDrawerState();
        }
      } catch (e: any) {
        if (isUnauthorized(e)) {
          redirectToLogin();
          return;
        }

        if (seq !== listRequestSeqRef.current) return;

        const st = e?.status;
        const msg = normalizeMsg(e?.message || "Не удалось загрузить список задач");
        setItems([]);
        setTotal(0);

        if (st === 403 && requestedScope === "team") {
          setPageError("Доступ к вкладке «Все задачи» запрещён.");
        } else {
          setPageError(st ? `(${st}) ${msg}` : msg);
        }
      } finally {
        if (seq === listRequestSeqRef.current) {
          setListLoading(false);
        }
      }
    },
    [offset, tab, taskScope, searchQuery, taskKind, selectedId, drawerMode, redirectToLogin, orgGroupId, orgUnitId, positionId, isSystemAdmin, resetDrawerState],
  );

  const loadTaskDetails = React.useCallback(
    async (taskId: number) => {
      const requestId = ++detailsRequestRef.current;
      setDrawerLoading(true);
      setDrawerError(null);

      try {
        const data = await apiGetTask({ taskId, includeArchived: true });

        if (detailsRequestRef.current !== requestId) return;

        setSelectedItem(data);
        const existingReportLink = resolveTaskReportLink(data);
        setReportLink(existingReportLink);
      } catch (e: any) {
        if (detailsRequestRef.current !== requestId) return;

        if (isUnauthorized(e)) {
          redirectToLogin();
          return;
        }

        const st = e?.status;
        const msg = normalizeMsg(e?.message || "Не удалось загрузить задачу");
        setDrawerError(st ? `(${st}) ${msg}` : msg);
      } finally {
        if (detailsRequestRef.current === requestId) {
          setDrawerLoading(false);
        }
      }
    },
    [redirectToLogin],
  );

  const handleRefresh = React.useCallback(() => {
    const defaultScope: TaskScope = defaultTaskScope(me);

    resetDrawerState();
    setPageError(null);
    setOffset(0);
    setTab("active");
    setTaskScope(defaultScope);
    setSearch("");
    setSearchQuery("");
    setTaskKind("all");

    router.replace("/tasks");
    void loadItems({
      offset: 0,
      statusTab: "active",
      taskScope: defaultScope,
      orgUnitId: "",
      search: "",
      taskKind: "all",
    });
  }, [me, resetDrawerState, router, loadItems]);

  React.useEffect(() => {
    void (async () => {
      if (!isAuthed()) {
        router.replace("/login");
        return;
      }

      try {
        const meInfo = await apiAuthMe();
        setMe(meInfo);
        setTaskScope(defaultTaskScope(meInfo));
      } catch (e: any) {
        if (isUnauthorized(e)) {
          redirectToLogin();
          return;
        }
        setPageError(normalizeMsg(e?.message || "Ошибка авторизации"));
        return;
      }

      const pid = await loadCurrentPeriod();
      if (pid > 0) {
        await loadManualRoleOptions(pid);
      }

      setReady(true);
    })();
  }, [router, redirectToLogin, loadCurrentPeriod, loadManualRoleOptions]);

  React.useEffect(() => {
    if (prevOrgUnitRef.current !== orgUnitId) {
      prevOrgUnitRef.current = orgUnitId;
      setOffset(0);
    }
  }, [orgUnitId]);

  React.useEffect(() => {
    if (prevOrgGroupRef.current !== orgGroupId) {
      prevOrgGroupRef.current = orgGroupId;
      setOffset(0);
    }
  }, [orgGroupId]);

  React.useEffect(() => {
    const timer = window.setTimeout(() => {
      setSearchQuery(search.trim());
      setOffset(0);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  React.useEffect(() => {
    if (!ready) return;
    if (!canSeeTeamTasks && taskScope === "team") {
      setTaskScope("mine");
    }
  }, [ready, canSeeTeamTasks, taskScope]);

  React.useEffect(() => {
    if (!ready) return;
    void loadItems();
  }, [ready, loadItems]);

  React.useEffect(() => {
    if (!ready || deepLinkTaskId == null) return;
    if (selectedId === deepLinkTaskId && drawerOpen && drawerMode === "view") return;

    setDrawerError(null);
    setUiNotice("");
    setReason("");
    setSelectedId(deepLinkTaskId);
    setSelectedItem(null);
    setReportLink("");
    setDrawerMode("view");
    setDrawerOpen(true);
    void loadTaskDetails(deepLinkTaskId);
  }, [ready, deepLinkTaskId, selectedId, drawerOpen, drawerMode, loadTaskDetails]);

  React.useEffect(() => {
    const src = selectedItem;
    if (!src) return;

    const approvedAt = src?.report_approved_at ?? null;
    const submittedAt = src?.report_submitted_at ?? null;

    if (approvedAt) {
      setUiNotice("Отчёт согласован.");
      return;
    }

    if (submittedAt) {
      setUiNotice("Отчёт отправлен на согласование.");
    }
  }, [selectedItem]);

  function openCreate() {
    setDrawerError(null);
    setUiNotice("");
    setReason("");
    setReportLink("");
    setSelectedId(null);
    setSelectedItem(null);
    setDrawerMode("create");
    setDrawerOpen(true);
  }

  function openView(task: any) {
    const taskId = taskIdOf(task);
    setDrawerError(null);
    setUiNotice("");
    setReason("");
    setSelectedId(taskId);
    setSelectedItem(task);
    setReportLink(resolveTaskReportLink(task));
    setDrawerMode("view");
    setDrawerOpen(true);
    void loadTaskDetails(taskId);
  }

  function openEdit(task: any) {
    if (readOnlyTeamMode) return;
    if (!canEditTask(task, { isSystemAdmin })) return;

    const taskId = taskIdOf(task);
    setDrawerError(null);
    setUiNotice("");
    setReason("");
    setSelectedId(taskId);
    setSelectedItem(task);
    setReportLink(resolveTaskReportLink(task));
    setDrawerMode("edit");
    setDrawerOpen(true);
    void loadTaskDetails(taskId);
  }

  async function handleSaveEdit(values: TaskEditValues) {
    if (!selectedId) return;

    const title = values.title.trim();
    if (!title) {
      setDrawerError("Название задачи обязательно.");
      return;
    }

    setSaving(true);
    setDrawerError(null);
    setUiNotice("");

    try {
      const dueDate = values.due_date.trim() || null;

      await apiFetchJson(`/tasks/${selectedId}`, {
        method: "PATCH",
        body: {
          title,
          description: values.description.trim() || null,
          source_note: values.source_note.trim() || null,
          due_date: dueDate,
          due_at: dueDate ? `${dueDate}T00:00:00` : null,
        },
      });

      setDrawerMode("view");
      setUiNotice("Изменения сохранены.");
      await Promise.all([loadTaskDetails(selectedId), loadItems()]);
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }

      const st = e?.status;
      const msg = normalizeMsg(e?.message || "Не удалось сохранить задачу");
      setDrawerError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(task: any, hard = false) {
    if (!isSystemAdmin) return;

    const taskId = taskIdOf(task);
    const ok = window.confirm(
      hard
        ? "Удалить задачу навсегда? Это физическое удаление и его нельзя отменить."
        : `Удалить задачу «${taskTitleOf(task)}»?`,
    );
    if (!ok) return;

    setSaving(true);
    setPageError(null);
    setDrawerError(null);
    setUiNotice("");

    try {
      await apiFetchJson(`/tasks/${taskId}`, {
        method: "DELETE",
        query: hard ? { hard: true } : undefined,
      });

      if (selectedId === taskId) {
        resetDrawerState();
      }

      await loadItems();
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }

      const st = e?.status;
      const msg = normalizeMsg(e?.message || "Не удалось удалить задачу");
      const text = st ? `(${st}) ${msg}` : msg;

      if (selectedId === taskId && drawerOpen) {
        setDrawerError(text);
      } else {
        setPageError(text);
      }
    } finally {
      setSaving(false);
    }
  }

  async function runAction(action: TaskAction) {
    if (!selectedId) return;

    setSaving(true);
    setDrawerError(null);
    setUiNotice("");

    try {
      if (action === "reject") {
        const r = reason.trim();
        if (!r) {
          setDrawerError("Отклонение: обязательно заполните примечание (причину).");
          return;
        }
      }

      if (action === "report") {
        const link = reportLink.trim();
        if (!link) {
          setDrawerError("Отчёт: укажите ссылку или путь.");
          return;
        }

        const existingLink = resolveTaskReportLink(selectedItem);
        if (existingLink && existingLink !== link) {
          const ok = window.confirm("Отчёт уже отправлен. Заменить ссылку?");
          if (!ok) return;
        }

        await apiPostTaskAction({
          taskId: selectedId,
          action,
          payload: {
            report_link: link,
            current_comment: reason.trim() ? reason.trim() : undefined,
            ...(reason.trim() ? ({ reason: reason.trim() } as any) : null),
          } as any,
        });

        setUiNotice("Отчёт отправлен на согласование.");
        setReason("");
      } else if (action === "approve") {
        await apiPostTaskAction({
          taskId: selectedId,
          action,
          payload: reason.trim() ? ({ reason: reason.trim() } as any) : undefined,
        });
        setUiNotice("Отчёт согласован.");
        setReason("");
      } else if (action === "reject") {
        await apiPostTaskAction({
          taskId: selectedId,
          action,
          payload: reason.trim() ? ({ reason: reason.trim() } as any) : undefined,
        });
        setUiNotice("Отчёт отклонён.");
      } else if (action === "archive") {
        await apiPostTaskAction({
          taskId: selectedId,
          action,
          payload: reason.trim() ? ({ reason: reason.trim() } as any) : undefined,
        });
        setUiNotice("Задача перемещена в архив.");
      }

      await Promise.all([loadTaskDetails(selectedId), loadItems()]);
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }

      const st = e?.status;
      const msg = normalizeMsg(e?.message || "Не удалось выполнить действие");
      setDrawerError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setSaving(false);
    }
  }

  const currentEditValues = React.useMemo<TaskEditValues>(() => {
    const src = selectedItem ?? {};
    return {
      title: String(src?.title ?? ""),
      description: String(src?.description ?? ""),
      source_note: String(src?.source_note ?? ""),
      due_date: toDateInputValue(src?.due_date ?? src?.due_at ?? src?.deadline ?? null),
    };
  }, [selectedItem]);

  const drawerTitle = React.useMemo(() => {
    if (drawerMode === "create") return "Создание записи";
    if (drawerMode === "edit") return "Редактирование записи";
    return selectedItem ? taskTitleOf(selectedItem) : "Карточка задачи";
  }, [drawerMode, selectedItem]);

  const drawerSubtitle =
    drawerMode === "create" ? "Задачи" : taskScope === "team" ? "Все задачи" : "Мои задачи";

  const selectedAllowed = React.useMemo(() => allowedActionsOf(selectedItem), [selectedItem]);
  const selectedEditable = React.useMemo(
    () => isTaskRowEditable(selectedItem, { readOnlyTeamMode, isSystemAdmin }),
    [selectedItem, readOnlyTeamMode, isSystemAdmin],
  );

  const tableColSpan = showExecutorColumn ? 7 : 6;

  return (
    <div className="bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="w-full px-0 py-0">
        <div className="overflow-hidden rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
          <div className="border-b border-zinc-200 dark:border-zinc-800 px-4 py-3">
            <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">Задачи</h1>
          </div>

          <div className="border-b border-zinc-200 dark:border-zinc-800 px-4 py-3">
            {showTaskOrgFilters ? (
              <div className="mb-3">
                <TaskOrgFiltersBar basePath="/tasks" visible />
              </div>
            ) : null}

            {canSeeTeamTasks ? (
              <div className="mb-3 flex items-center gap-1 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-1">
                <button
                  type="button"
                  onClick={() => {
                    setTaskScope((prev) => (prev === "team" ? "mine" : "team"));
                    setOffset(0);
                    resetDrawerState();
                  }}
                  className={[
                    "rounded-md px-3 py-2 text-sm transition",
                    taskScope === "team"
                      ? "bg-zinc-200 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-50"
                      : "text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700",
                  ].join(" ")}
                >
                  Все задачи
                </button>
              </div>
            ) : null}

            <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
              <div className="flex-1">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={
                    taskScope === "team"
                      ? "Поиск по задаче, роли или исполнителю"
                      : "Поиск по названию задачи"
                  }
                  className="h-10 w-full rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                />
              </div>

              <select
                value={taskKind}
                onChange={(e) => {
                  setTaskKind(e.target.value as TaskKindFilter);
                  setOffset(0);
                }}
                className="h-10 min-w-[180px] rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
              >
                {TASK_KIND_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value} className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                    {opt.label}
                  </option>
                ))}
              </select>

              <div className="flex items-center gap-1 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-1">
                {(["active", "done", "rejected"] as StatusTab[]).map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => {
                      setTab(v);
                      setOffset(0);
                    }}
                    className={[
                      "rounded-md px-3 py-2 text-sm transition",
                      tab === v ? "bg-zinc-200 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-50" : "text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700",
                    ].join(" ")}
                  >
                    {tabRu(v)}
                  </button>
                ))}
              </div>

              <button
                type="button"
                onClick={handleRefresh}
                className="h-10 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
              >
                Обновить
              </button>

              {canCreateManualTask && taskScope === "mine" ? (
                <button
                  type="button"
                  onClick={openCreate}
                  disabled={!currentPeriodId || manualRolesLoading}
                  className="h-10 rounded-lg bg-blue-600 px-5 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Создать
                </button>
              ) : null}
            </div>
          </div>

          <div className="px-4 py-4">
            {!!pageError && (
              <div className="mb-4 rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
                {pageError}
              </div>
            )}

            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm text-zinc-600 dark:text-zinc-400">
              <div>
                {scopeRu(taskScope)} · Всего: {displayTotal} · Показано: {displayItems.length}
                {listLoading ? <span className="ml-2">· загрузка…</span> : null}
                {manualRolesLoading ? <span className="ml-2">· роли…</span> : null}
              </div>

              <div className="text-zinc-600 dark:text-zinc-400">
                Период: {currentPeriodName ? `${currentPeriodName} (#${currentPeriodId})` : `#${currentPeriodId}`}
              </div>
            </div>

            <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
              <div className="overflow-x-auto">
                <table className="w-full table-fixed border-collapse">
                  <colgroup>
                    <col className="w-[48px]" />
                    <col className="w-[280px]" />
                    <col className="w-[108px]" />
                    {showExecutorColumn ? <col className="w-[200px]" /> : null}
                    <col className="w-[92px]" />
                    <col className="w-[92px]" />
                    <col className={actionsColWidth} />
                  </colgroup>

                  <thead>
                    <tr className="bg-zinc-100 dark:bg-zinc-900 text-left">
                      <th className="px-1.5 py-3 text-xs font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        ID
                      </th>
                      <th className="px-1.5 py-3 text-xs font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        Название
                      </th>

                      <th className="px-2 py-3 text-xs font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        Периодичность
                      </th>

                      {showExecutorColumn ? (
                        <th className="px-1.5 py-3 text-xs font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                          Роль
                        </th>
                      ) : null}

                      <th className="px-2 py-3 text-xs font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        Статус
                      </th>
                      <th className="px-2 py-3 text-xs font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        Дедлайн
                      </th>
                      <th className="px-2 py-3 text-center text-xs font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                        Действия
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {listLoading ? (
                      <tr>
                        <td colSpan={tableColSpan} className="px-2 py-3 text-sm text-zinc-600 dark:text-zinc-400">
                          Загрузка...
                        </td>
                      </tr>
                    ) : displayItems.length === 0 ? (
                      <tr>
                        <td colSpan={tableColSpan} className="px-2 py-3 text-sm text-zinc-600 dark:text-zinc-400">
                          Записи не найдены.
                        </td>
                      </tr>
                    ) : (
                      displayItems.map((item) => {
                        const id = taskIdOf(item);
                        const editable = isTaskRowEditable(item, {
                          readOnlyTeamMode,
                          isSystemAdmin,
                        });
                        const displayColor = getTaskDisplayColor(item);

                        return (
                          <tr
                            key={id}
                            className="cursor-pointer border-t border-zinc-200 dark:border-zinc-800 align-middle transition hover:bg-zinc-100 dark:hover:bg-zinc-800"
                            onClick={() => openView(item)}
                          >
                            <td className="px-1.5 py-2 text-sm leading-5 text-zinc-900 dark:text-zinc-50">{id}</td>

                            <td className={`px-2 py-2 text-sm leading-5 ${taskDisplayColorTitleClass(displayColor)}`}>
                              <div className="max-w-full whitespace-normal break-words">{taskTitleOf(item)}</div>
                            </td>

                            <td
                              className="px-2 py-2 text-sm leading-5 text-zinc-600 dark:text-zinc-400"
                              data-testid={`task-periodicity-${id}`}
                            >
                              <span className="whitespace-nowrap">{taskPeriodicityLabel(item)}</span>
                            </td>

                            {showExecutorColumn ? (
                              <td className="px-1.5 py-2 text-sm leading-5 text-zinc-700 dark:text-zinc-300">
                                <div className="whitespace-normal break-words">
                                  {executorRoleLabelOf(item)}
                                </div>
                              </td>
                            ) : null}

                            <td className="px-2 py-2 text-sm leading-5 text-zinc-600 dark:text-zinc-400">
                              {statusTextOf(item)}
                            </td>

                            <td className={`px-2 py-2 text-sm leading-5 ${taskDisplayColorDeadlineClass(displayColor)}`}>
                              {formatDeadline(item)}
                            </td>

                            <td className="px-2 py-2">
                              <div className="flex items-center justify-center gap-1.5">
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    openView(item);
                                  }}
                                  className="rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2 py-1.5 text-[13px] leading-4 text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
                                >
                                  Открыть
                                </button>

                                {editable ? (
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      openEdit(item);
                                    }}
                                    title={editButtonTitle(item)}
                                    className="rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2.5 py-1.5 text-sm leading-5 text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
                                  >
                                    Изменить
                                  </button>
                                ) : null}

                                {showDeleteButtons ? (
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      void handleDelete(item, false);
                                    }}
                                    className="rounded-md border border-red-300 dark:border-red-800 bg-transparent px-2 py-1.5 text-[13px] leading-4 text-red-700 dark:text-red-300 transition hover:bg-red-50 dark:bg-red-950/35"
                                  >
                                    Удалить
                                  </button>
                                ) : null}
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setOffset((v) => Math.max(0, v - LIST_LIMIT))}
                className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
                disabled={listLoading || offset <= 0}
              >
                Назад
              </button>

              <button
                type="button"
                onClick={() => setOffset((v) => v + LIST_LIMIT)}
                className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
                disabled={listLoading || offset + LIST_LIMIT >= total}
              >
                Далее
              </button>
            </div>
          </div>
        </div>
      </div>

      <TaskDrawer open={drawerOpen} title={drawerTitle} subtitle={drawerSubtitle} onClose={closeDrawer}>
        {drawerMode === "create" ? (
          <div className="h-full px-6 py-5">
            <CreateManualTaskModal
              periodId={currentPeriodId}
              roleOptions={manualRoleOptions}
              onCreated={() => {
                resetDrawerState();
                setOffset(0);
                void loadItems({ offset: 0 });
              }}
            />
          </div>
        ) : drawerMode === "edit" ? (
          drawerLoading && !selectedItem ? (
            <div className="px-6 py-5 text-sm text-zinc-600 dark:text-zinc-400">Загрузка...</div>
          ) : (
            <TaskEditForm
              initialValues={currentEditValues}
              isSystemAdmin={isSystemAdmin}
              saving={saving}
              error={drawerError}
              onCancel={closeDrawer}
              onSubmit={handleSaveEdit}
              reportSection={
                selectedAllowed.includes("report")
                  ? {
                      link: reportLink,
                      onLinkChange: setReportLink,
                      comment: reason,
                      onCommentChange: setReason,
                      onSend: () => void runAction("report"),
                      disabled: saving || drawerLoading,
                    }
                  : undefined
              }
            />
          )
        ) : (
          <TaskDetailPanel
            drawerLoading={drawerLoading}
            selectedItem={selectedItem}
            drawerError={drawerError}
            uiNotice={uiNotice}
            showExecutorColumn={showExecutorColumn}
            selectedEditable={selectedEditable}
            showDeleteButtons={showDeleteButtons}
            isSystemAdmin={isSystemAdmin}
            saving={saving}
            reportLink={reportLink}
            reason={reason}
            onReportLinkChange={setReportLink}
            onReasonChange={setReason}
            onEdit={() => setDrawerMode("edit")}
            onDelete={(permanent) => {
              if (selectedItem) void handleDelete(selectedItem, permanent);
            }}
            onRunAction={(action) => void runAction(action)}
          />
        )}
      </TaskDrawer>
    </div>
  );
}