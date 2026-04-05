// FILE: corpsite-ui/app/tasks/_components/TasksPageClient.tsx
"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { apiAuthMe, apiFetchJson, apiGetTask, apiPostTaskAction } from "@/lib/api";
import { isAuthed, logout } from "@/lib/auth";

import CreateManualTaskModal, { type ManualTaskRoleOption } from "./CreateManualTaskModal";
import TaskDrawer from "./TaskDrawer";
import TaskEditForm, { type TaskEditValues } from "./TaskEditForm";

const ACTION_RU: Record<string, string> = {
  report: "Отправить отчёт",
  approve: "Согласовать",
  reject: "Отклонить",
  archive: "В архив",
};

const LIST_LIMIT = 50;

type AllowedAction = "report" | "approve" | "reject" | "archive";
type TaskAction = AllowedAction;
type StatusTab = "active" | "done" | "rejected";
type DrawerMode = "create" | "view" | "edit";
type TaskKindFilter = "all" | "adhoc" | "regular" | "other";
type TaskScope = "mine" | "team";

type MeInfo = {
  user_id?: number;
  role_id?: number;
  role_code?: string;
  role_name?: string;
  role_name_ru?: string;
  full_name?: string;
  login?: string;
};

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
  orgUnitId?: string;
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
  const sCode = String(t?.status_code ?? "").trim();
  const sLegacy = String(t?.status ?? "").trim();
  if (sRu) return sRu;
  if (sCode) return sCode;
  if (sLegacy) return sLegacy;
  const sid = t?.status_id;
  if (sid != null) return `status_id=${sid}`;
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

function actionsRu(actions: AllowedAction[] | undefined | null): string {
  if (!actions || actions.length === 0) return "—";
  return actions.map((a) => ACTION_RU[String(a)] ?? String(a)).join(" / ");
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

function fmtDtRu(raw: any): string {
  if (!raw) return "";
  const s = String(raw).trim();
  if (!s) return "";

  const d = new Date(s);
  if (!Number.isFinite(d.getTime())) return s;

  try {
    return d.toLocaleString("ru-RU");
  } catch {
    return s;
  }
}

function roleLabelOfReport(src: any, kind: "submitted" | "approved"): string {
  const nameKey = kind === "submitted" ? "report_submitted_by_role_name" : "report_approved_by_role_name";
  const codeKey = kind === "submitted" ? "report_submitted_by_role_code" : "report_approved_by_role_code";
  const idKey = kind === "submitted" ? "report_submitted_by" : "report_approved_by";

  const name = String(src?.[nameKey] ?? "").trim();
  if (name) return name;

  const code = String(src?.[codeKey] ?? "").trim();
  if (code) return code;

  const id = src?.[idKey];
  if (id != null && String(id).trim()) return `ID ${String(id)}`;

  return "—";
}

function isHttpUrl(s: string): boolean {
  const v = (s || "").trim();
  return /^https?:\/\//i.test(v);
}

function isUncPath(s: string): boolean {
  const v = (s || "").trim();
  return /^\\\\[^\\]+\\.+/i.test(v);
}

function isWindowsDrivePath(s: string): boolean {
  const v = (s || "").trim();
  return /^[a-zA-Z]:\\/.test(v);
}

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {}

  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    ta.style.top = "-9999px";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

type ReportUiState = "none" | "draft" | "sent_waiting" | "approved" | "rejected_or_archived";

function computeReportUiState(src: any): ReportUiState {
  const statusCode = String(src?.status_code ?? "").trim().toUpperCase();
  const link = String(src?.report_link ?? "").trim();
  const submittedAt = src?.report_submitted_at ?? null;
  const approvedAt = src?.report_approved_at ?? null;

  if (statusCode === "ARCHIVED") return "rejected_or_archived";
  if (statusCode === "REJECTED") return "rejected_or_archived";
  if (approvedAt) return "approved";

  const sent = Boolean(submittedAt) || Boolean(link);
  if (sent) return "sent_waiting";

  return "draft";
}

function reportStatusBadgeText(st: ReportUiState): string {
  if (st === "approved") return "Отчёт согласован";
  if (st === "sent_waiting") return "Отчёт отправлен на согласование";
  if (st === "draft") return "Отчёт не отправлен";
  if (st === "rejected_or_archived") return "Задача отклонена/в архиве";
  return "—";
}

function reportStatusBadgeClass(st: ReportUiState): string {
  if (st === "approved") return "border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200";
  if (st === "sent_waiting") return "border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200";
  if (st === "draft") return "border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-zinc-700 dark:text-zinc-300";
  if (st === "rejected_or_archived") return "border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-zinc-600 dark:text-zinc-400";
  return "border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-zinc-600 dark:text-zinc-400";
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

function detectSystemAdmin(me: MeInfo | null): boolean {
  const roleId = Number(me?.role_id ?? 0);
  const roleCode = String(me?.role_code ?? "").trim().toUpperCase();
  const roleName = String(me?.role_name ?? "").trim().toLowerCase();
  const roleNameRu = String(me?.role_name_ru ?? "").trim().toLowerCase();

  if (roleId === 2) return true;
  if (roleCode === "ADMIN" || roleCode === "SYSTEM_ADMIN") return true;
  if (roleName.includes("system administrator")) return true;
  if (roleNameRu.includes("системный администратор")) return true;

  return false;
}

function detectCanSeeTeamTasks(me: MeInfo | null): boolean {
  const roleId = Number(me?.role_id ?? 0);
  const roleCode = String(me?.role_code ?? "").trim().toUpperCase();
  const roleName = String(me?.role_name ?? "").trim().toLowerCase();
  const roleNameRu = String(me?.role_name_ru ?? "").trim().toLowerCase();

  if (roleId === 2) return true;
  if (roleCode.includes("DIRECTOR")) return true;
  if (roleCode.includes("DEPUTY")) return true;
  if (roleCode.endsWith("_HEAD")) return true;
  if (roleNameRu.includes("руководител")) return true;
  if (roleNameRu.includes("директор")) return true;
  if (roleNameRu.includes("заместител")) return true;
  if (roleName.includes("head")) return true;
  if (roleName.includes("director")) return true;
  if (roleName.includes("deputy")) return true;

  return false;
}

function canEditTask(src: any): boolean {
  const taskKind = String(src?.task_kind ?? "").trim().toLowerCase();
  const statusCode = String(src?.status_code ?? "").trim().toUpperCase();

  if (!src) return false;
  if (statusCode === "ARCHIVED") return false;

  return taskKind === "adhoc" || taskKind === "regular";
}

function editButtonTitle(src: any): string {
  const taskKind = String(src?.task_kind ?? "").trim().toLowerCase();
  const statusCode = String(src?.status_code ?? "").trim().toUpperCase();

  if (!src) return "Сначала выберите задачу";
  if (statusCode === "ARCHIVED") return "Архивная задача не редактируется";
  if (taskKind === "adhoc" || taskKind === "regular") return "Редактировать выбранную задачу";
  return "Этот тип задачи не поддерживает редактирование";
}

function normalizeText(value: string): string {
  return String(value || "").toLowerCase().replace(/ё/g, "е").trim();
}

function matchesSearch(name: string, query: string): boolean {
  const q = normalizeText(query);
  if (!q) return true;

  const hay = normalizeText(name);
  if (hay.includes(q)) return true;

  const tokens = q.split(/\s+/).filter(Boolean);
  return tokens.every((t) => hay.includes(t));
}

function normalizeTaskKind(value: any): string {
  const s = String(value ?? "").trim().toLowerCase();
  if (s === "adhoc" || s === "regular") return s;
  return s ? "other" : "";
}

function taskKindLabelOf(src: any): string {
  const v = normalizeTaskKind(src?.task_kind);
  if (v === "adhoc") return "Разовая";
  if (v === "regular") return "Регулярная";
  if (v === "other") return "Прочее";
  return "—";
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

function executorPersonLabelOf(src: any): string {
  return String(src?.executor_name ?? "").trim();
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
  const [copyHint, setCopyHint] = React.useState("");
  const [uiNotice, setUiNotice] = React.useState("");

  const [currentPeriodId, setCurrentPeriodId] = React.useState<number>(3);
  const [currentPeriodName, setCurrentPeriodName] = React.useState("");

  const [manualRoleOptions, setManualRoleOptions] = React.useState<ManualTaskRoleOption[]>([]);
  const [canCreateManualTask, setCanCreateManualTask] = React.useState(false);
  const [manualRolesLoading, setManualRolesLoading] = React.useState(false);

  const orgUnitId = sp.get("org_unit_id") ?? "";
  const prevOrgUnitRef = React.useRef<string>(orgUnitId);

  const isSystemAdmin = React.useMemo(() => detectSystemAdmin(me), [me]);
  const canSeeTeamTasks = React.useMemo(() => detectCanSeeTeamTasks(me), [me]);

  const readOnlyTeamMode = taskScope === "team" && !isSystemAdmin;
  const showExecutorColumn = taskScope === "team";
  const showDeleteButtons = isSystemAdmin;
  const actionsColWidth = showDeleteButtons ? "w-[170px]" : "w-[138px]";

  const filteredItems = React.useMemo(() => {
    return items.filter((item) => {
      const q = search.trim();
      const bySearch = !q
        ? true
        : matchesSearch(taskTitleOf(item), q) ||
          (taskScope === "team" &&
            (matchesSearch(executorRoleLabelOf(item), q) ||
              matchesSearch(String(item?.executor_name ?? ""), q)));

      const kindValue = normalizeTaskKind(item?.task_kind);
      const byTaskKind = taskKind === "all" ? true : kindValue === taskKind;
      return bySearch && byTaskKind;
    });
  }, [items, search, taskKind, taskScope]);

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
    setCopyHint("");
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
  }, [saving, resetDrawerState]);

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
        const qOrgUnitId = typeof options?.orgUnitId === "string" ? options.orgUnitId : orgUnitId;

        const body = await apiFetchJson<any>("/tasks", {
          query: {
            scope: requestedScope,
            limit: LIST_LIMIT,
            offset: qOffset,
            status_filter: qStatusTab,
            org_unit_id: qOrgUnitId || undefined,
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
    [offset, tab, taskScope, selectedId, drawerMode, redirectToLogin, orgUnitId, resetDrawerState],
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
        const existingReportLink = String((data as any)?.report_link ?? "").trim();
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
    const defaultScope: TaskScope = canSeeTeamTasks ? "team" : "mine";

    resetDrawerState();
    setPageError(null);
    setOffset(0);
    setTab("active");
    setTaskScope(defaultScope);
    setSearch("");
    setTaskKind("all");

    router.replace("/tasks");
    void loadItems({
      offset: 0,
      statusTab: "active",
      taskScope: defaultScope,
      orgUnitId: "",
    });
  }, [canSeeTeamTasks, resetDrawerState, router, loadItems]);

  React.useEffect(() => {
    void (async () => {
      if (!isAuthed()) {
        router.replace("/login");
        return;
      }

      try {
        const meBody = await apiAuthMe();
        const meInfo = meBody as MeInfo;
        setMe(meInfo);
        setTaskScope(detectCanSeeTeamTasks(meInfo) ? "team" : "mine");
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
    setCopyHint("");
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
    setCopyHint("");
    setReason("");
    setSelectedId(taskId);
    setSelectedItem(task);
    setReportLink(String(task?.report_link ?? "").trim());
    setDrawerMode("view");
    setDrawerOpen(true);
    void loadTaskDetails(taskId);
  }

  function openEdit(task: any) {
    if (readOnlyTeamMode) return;
    if (!canEditTask(task)) return;

    const taskId = taskIdOf(task);
    setDrawerError(null);
    setUiNotice("");
    setCopyHint("");
    setReason("");
    setSelectedId(taskId);
    setSelectedItem(task);
    setReportLink(String(task?.report_link ?? "").trim());
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

        const existingLink = String(selectedItem?.report_link ?? "").trim();
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
  const selectedStatus = React.useMemo(() => statusTextOf(selectedItem), [selectedItem]);
  const selectedEditable = React.useMemo(
    () => canEditTask(selectedItem) && !readOnlyTeamMode,
    [selectedItem, readOnlyTeamMode],
  );

  const selectedReportUiState = React.useMemo(
    () => computeReportUiState(selectedItem),
    [selectedItem],
  );

  const tableColSpan = showExecutorColumn ? 6 : 5;
  const selectedExecutorRole = React.useMemo(() => executorRoleLabelOf(selectedItem), [selectedItem]);
  const selectedExecutorPerson = React.useMemo(() => executorPersonLabelOf(selectedItem), [selectedItem]);

  return (
    <div className="bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="w-full px-0 py-0">
        <div className="overflow-hidden rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
          <div className="border-b border-zinc-200 dark:border-zinc-800 px-4 py-3">
            <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">Задачи</h1>
          </div>

          <div className="border-b border-zinc-200 dark:border-zinc-800 px-4 py-3">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-1 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-1">
                {canSeeTeamTasks ? (
                  <button
                    type="button"
                    onClick={() => {
                      setTaskScope("team");
                      setOffset(0);
                      resetDrawerState();
                    }}
                    className={[
                      "rounded-md px-3 py-2 text-sm transition",
                      taskScope === "team" ? "bg-zinc-200 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-50" : "text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700",
                    ].join(" ")}
                  >
                    Все задачи
                  </button>
                ) : null}

                <button
                  type="button"
                  onClick={() => {
                    setTaskScope("mine");
                    setOffset(0);
                    resetDrawerState();
                  }}
                  className={[
                    "rounded-md px-3 py-2 text-sm transition",
                    taskScope === "mine" ? "bg-zinc-200 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-50" : "text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700",
                  ].join(" ")}
                >
                  Мои задачи
                </button>
              </div>
            </div>

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
                onChange={(e) => setTaskKind(e.target.value as TaskKindFilter)}
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
                {scopeRu(taskScope)} · Всего: {total} · Показано: {filteredItems.length}
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
                    <col className="w-[300px]" />
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
                    ) : filteredItems.length === 0 ? (
                      <tr>
                        <td colSpan={tableColSpan} className="px-2 py-3 text-sm text-zinc-600 dark:text-zinc-400">
                          Записи не найдены.
                        </td>
                      </tr>
                    ) : (
                      filteredItems.map((item) => {
                        const id = taskIdOf(item);
                        const editable = canEditTask(item) && !readOnlyTeamMode;

                        return (
                          <tr
                            key={id}
                            className="cursor-pointer border-t border-zinc-200 dark:border-zinc-800 align-middle transition hover:bg-zinc-100 dark:hover:bg-zinc-800"
                            onClick={() => openView(item)}
                          >
                            <td className="px-1.5 py-2 text-sm leading-5 text-zinc-900 dark:text-zinc-50">{id}</td>

                            <td className="px-2 py-2 text-sm leading-5 text-zinc-900 dark:text-zinc-50">
                              <div className="max-w-full whitespace-normal break-words">{taskTitleOf(item)}</div>
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

                            <td className="px-2 py-2 text-sm leading-5 text-zinc-600 dark:text-zinc-400">
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
                disabled={listLoading || items.length < LIST_LIMIT}
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
          <div className="flex h-full flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
            <div className="flex-1 overflow-y-auto px-6 py-5">
              {drawerLoading && !selectedItem ? (
                <div className="text-sm text-zinc-600 dark:text-zinc-400">Загрузка...</div>
              ) : !selectedItem ? (
                <div className="text-sm text-zinc-600 dark:text-zinc-400">Задача не выбрана.</div>
              ) : (
                <div className="space-y-5">
                  {!!drawerError && (
                    <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
                      {drawerError}
                    </div>
                  )}

                  {!!uiNotice && (
                    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-3 text-sm text-zinc-800 dark:text-zinc-200">
                      {uiNotice}
                    </div>
                  )}

                  <div className="flex flex-wrap items-center gap-2">
                    <div className="rounded-md border border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900 px-2 py-1 text-xs text-zinc-800 dark:text-zinc-200">
                      {selectedStatus}
                    </div>

                    <div
                      className={[
                        "rounded-md border px-2 py-1 text-xs",
                        reportStatusBadgeClass(selectedReportUiState),
                      ].join(" ")}
                    >
                      {reportStatusBadgeText(selectedReportUiState)}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                      <div className="text-xs text-zinc-600 dark:text-zinc-400">ID</div>
                      <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{taskIdOf(selectedItem)}</div>
                    </div>

                    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                      <div className="text-xs text-zinc-600 dark:text-zinc-400">Дедлайн</div>
                      <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{formatDeadline(selectedItem)}</div>
                    </div>

                    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                      <div className="text-xs text-zinc-600 dark:text-zinc-400">Тип задачи</div>
                      <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{taskKindLabelOf(selectedItem)}</div>
                    </div>

                    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                      <div className="text-xs text-zinc-600 dark:text-zinc-400">Источник</div>
                      <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">
                        {String(selectedItem?.source_kind ?? "—")}
                      </div>
                    </div>

                    {showExecutorColumn ? (
                      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4 sm:col-span-2">
                        <div className="text-xs text-zinc-600 dark:text-zinc-400">Роль</div>
                        <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{selectedExecutorRole}</div>
                        {selectedExecutorPerson && selectedExecutorPerson !== selectedExecutorRole ? (
                          <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">{selectedExecutorPerson}</div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>

                  {String(selectedItem?.description ?? "").trim() ? (
                    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                      <div className="text-xs text-zinc-600 dark:text-zinc-400">Описание</div>
                      <div className="mt-2 whitespace-pre-wrap text-sm text-zinc-900 dark:text-zinc-50">
                        {String(selectedItem?.description ?? "").trim()}
                      </div>
                    </div>
                  ) : null}

                  {String(selectedItem?.source_note ?? "").trim() ? (
                    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                      <div className="text-xs text-zinc-600 dark:text-zinc-400">Примечание</div>
                      <div className="mt-2 whitespace-pre-wrap text-sm text-zinc-900 dark:text-zinc-50">
                        {String(selectedItem?.source_note ?? "").trim()}
                      </div>
                    </div>
                  ) : null}

                  <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                    <div className="mb-1 text-xs text-zinc-600 dark:text-zinc-400">Доступные действия</div>
                    <div className="text-sm text-zinc-900 dark:text-zinc-50">{actionsRu(selectedAllowed)}</div>
                  </div>

                  {String(selectedItem?.report_link ?? "").trim() ? (
                    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                      <div className="mb-2 text-xs text-zinc-600 dark:text-zinc-400">Отчёт</div>

                      {isHttpUrl(String(selectedItem?.report_link ?? "").trim()) ? (
                        <a
                          href={String(selectedItem?.report_link ?? "").trim()}
                          target="_blank"
                          rel="noreferrer"
                          className="break-all text-sm text-blue-600 dark:text-blue-400 underline"
                        >
                          Открыть отчёт
                        </a>
                      ) : (
                        <div className="space-y-2">
                          <div className="break-all text-sm text-zinc-800 dark:text-zinc-200">
                            {String(selectedItem?.report_link ?? "").trim()}
                          </div>

                          <div className="flex flex-wrap items-center gap-2">
                            <button
                              type="button"
                              onClick={async () => {
                                const raw = String(selectedItem?.report_link ?? "").trim();
                                const ok = await copyToClipboard(raw);
                                setCopyHint(ok ? "Путь скопирован" : "Не удалось скопировать");
                                window.setTimeout(() => setCopyHint(""), 1500);
                              }}
                              className="rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-xs text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700"
                            >
                              Скопировать путь
                            </button>

                            {isUncPath(String(selectedItem?.report_link ?? "").trim()) ||
                            isWindowsDrivePath(String(selectedItem?.report_link ?? "").trim()) ? (
                              <div className="text-xs text-zinc-600 dark:text-zinc-400">
                                UNC/локальный путь не открывается браузером напрямую.
                              </div>
                            ) : (
                              <div className="text-xs text-zinc-600 dark:text-zinc-400">Ссылка не является http(s).</div>
                            )}

                            {copyHint ? <div className="text-xs text-zinc-600 dark:text-zinc-400">• {copyHint}</div> : null}
                          </div>
                        </div>
                      )}

                      {selectedItem?.report_submitted_at ? (
                        <div className="mt-3 text-xs text-zinc-600 dark:text-zinc-400">
                          Отчёт отправлен:{" "}
                          <span className="text-zinc-800 dark:text-zinc-200">{fmtDtRu(selectedItem?.report_submitted_at)}</span>
                        </div>
                      ) : null}

                      {selectedItem?.report_submitted_by ? (
                        <div className="text-xs text-zinc-600 dark:text-zinc-400">
                          Отправил:{" "}
                          <span className="text-zinc-800 dark:text-zinc-200">
                            {roleLabelOfReport(selectedItem, "submitted")}
                          </span>
                        </div>
                      ) : null}

                      {selectedItem?.report_approved_at ? (
                        <div className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
                          Решение принято:{" "}
                          <span className="text-zinc-800 dark:text-zinc-200">{fmtDtRu(selectedItem?.report_approved_at)}</span>
                        </div>
                      ) : null}

                      {selectedItem?.report_approved_by ? (
                        <div className="text-xs text-zinc-600 dark:text-zinc-400">
                          Принял решение:{" "}
                          <span className="text-zinc-800 dark:text-zinc-200">
                            {roleLabelOfReport(selectedItem, "approved")}
                          </span>
                        </div>
                      ) : null}

                      {String(selectedItem?.report_current_comment ?? "").trim() ? (
                        <div className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
                          Комментарий:{" "}
                          <span className="text-zinc-800 dark:text-zinc-200">
                            {String(selectedItem?.report_current_comment ?? "").trim()}
                          </span>
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {selectedAllowed.includes("report") ? (
                    <div className="flex flex-col gap-2">
                      <label className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Ссылка или путь на отчёт</label>
                      <input
                        value={reportLink}
                        onChange={(e) => setReportLink(e.target.value)}
                        placeholder="https://... или \\server\share\... или d:\..."
                        className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                      />
                    </div>
                  ) : null}

                  {selectedAllowed.length > 0 ? (
                    <div className="flex flex-col gap-2">
                      <label className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Причина / комментарий</label>
                      <textarea
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        rows={4}
                        placeholder="Комментарий для действия"
                        className="min-h-[96px] resize-y rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-3 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                      />
                    </div>
                  ) : null}
                </div>
              )}
            </div>

            {selectedItem ? (
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-200 dark:border-zinc-800 px-6 py-4">
                <div className="text-sm text-zinc-600 dark:text-zinc-400">{actionsRu(selectedAllowed)}</div>

                <div className="flex flex-wrap items-center gap-2">
                  {selectedEditable ? (
                    <button
                      type="button"
                      onClick={() => setDrawerMode("edit")}
                      disabled={saving || drawerLoading}
                      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
                    >
                      Изменить
                    </button>
                  ) : null}

                  {showDeleteButtons ? (
                    <button
                      type="button"
                      onClick={() => void handleDelete(selectedItem, false)}
                      disabled={saving || drawerLoading}
                      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
                    >
                      Удалить
                    </button>
                  ) : null}

                  {isSystemAdmin ? (
                    <button
                      type="button"
                      onClick={() => void handleDelete(selectedItem, true)}
                      disabled={saving || drawerLoading}
                      className="rounded-lg border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-2 text-sm text-red-800 dark:text-red-200 transition hover:bg-red-50 dark:bg-red-950/35 disabled:opacity-60"
                    >
                      Удалить навсегда
                    </button>
                  ) : null}

                  {selectedAllowed.includes("report") ? (
                    <button
                      type="button"
                      onClick={() => void runAction("report")}
                      disabled={saving || drawerLoading}
                      className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-60"
                    >
                      {ACTION_RU.report}
                    </button>
                  ) : null}

                  {selectedAllowed.includes("approve") ? (
                    <button
                      type="button"
                      onClick={() => void runAction("approve")}
                      disabled={saving || drawerLoading}
                      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
                    >
                      {ACTION_RU.approve}
                    </button>
                  ) : null}

                  {selectedAllowed.includes("reject") ? (
                    <button
                      type="button"
                      onClick={() => void runAction("reject")}
                      disabled={saving || drawerLoading}
                      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
                    >
                      {ACTION_RU.reject}
                    </button>
                  ) : null}

                  {selectedAllowed.includes("archive") ? (
                    <button
                      type="button"
                      onClick={() => {
                        const ok = window.confirm("Переместить задачу в архив?");
                        if (ok) void runAction("archive");
                      }}
                      disabled={saving || drawerLoading}
                      className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
                    >
                      {ACTION_RU.archive}
                    </button>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </TaskDrawer>
    </div>
  );
}