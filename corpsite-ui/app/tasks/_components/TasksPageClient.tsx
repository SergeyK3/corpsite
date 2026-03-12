// FILE: corpsite-ui/app/tasks/_components/TasksPageClient.tsx
"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

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
  const a = t?.allowed_actions;
  if (Array.isArray(a)) return a.filter(Boolean) as AllowedAction[];
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
  if (st === "approved") return "border-zinc-700 bg-zinc-950/40 text-zinc-200";
  if (st === "sent_waiting") return "border-zinc-700 bg-zinc-950/40 text-zinc-200";
  if (st === "draft") return "border-zinc-800 bg-zinc-950/20 text-zinc-300";
  if (st === "rejected_or_archived") return "border-zinc-800 bg-zinc-950/20 text-zinc-400";
  return "border-zinc-800 bg-zinc-950/20 text-zinc-400";
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

  if (roleId === 1) return true;
  if (roleCode === "ADMIN" || roleCode === "SYSTEM_ADMIN") return true;
  if (roleName.includes("system administrator")) return true;
  if (roleNameRu.includes("системный администратор")) return true;

  return false;
}

function canEditTask(src: any, isSystemAdmin: boolean): boolean {
  const taskKind = String(src?.task_kind ?? "").trim().toLowerCase();
  const sourceKind = String(src?.source_kind ?? "").trim().toLowerCase();
  const statusCode = String(src?.status_code ?? "").trim().toUpperCase();

  if (!src) return false;
  if (statusCode === "ARCHIVED") return false;

  if (isSystemAdmin) {
    return taskKind === "adhoc" || taskKind === "regular";
  }

  if (taskKind !== "adhoc") return false;
  if (sourceKind && !["manual", "bot", "import"].includes(sourceKind)) return false;

  return true;
}

function editButtonTitle(src: any, isSystemAdmin: boolean): string {
  const taskKind = String(src?.task_kind ?? "").trim().toLowerCase();
  const statusCode = String(src?.status_code ?? "").trim().toUpperCase();

  if (!src) return "Сначала выберите задачу";
  if (statusCode === "ARCHIVED") return "Архивная задача не редактируется";

  if (isSystemAdmin) {
    if (taskKind === "adhoc" || taskKind === "regular") return "Редактировать выбранную задачу";
    return "Этот тип задачи не поддерживает редактирование";
  }

  if (taskKind !== "adhoc") return "Только разовые задачи доступны для редактирования";
  return "Редактировать выбранную задачу";
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

const TASK_KIND_OPTIONS: Array<{ value: TaskKindFilter; label: string }> = [
  { value: "all", label: "Все типы" },
  { value: "adhoc", label: "Разовые" },
  { value: "regular", label: "Регулярные" },
  { value: "other", label: "Прочие" },
];

export default function TasksPageClient() {
  const router = useRouter();
  const detailsRequestRef = React.useRef(0);

  const [ready, setReady] = React.useState(false);
  const [me, setMe] = React.useState<MeInfo | null>(null);

  const [offset, setOffset] = React.useState(0);
  const [tab, setTab] = React.useState<StatusTab>("active");
  const [search, setSearch] = React.useState("");
  const [taskKind, setTaskKind] = React.useState<TaskKindFilter>("all");

  const [items, setItems] = React.useState<any[]>([]);
  const [total, setTotal] = React.useState(0);
  const [listLoading, setListLoading] = React.useState(false);
  const [pageError, setPageError] = React.useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerMode, setDrawerMode] = React.useState<DrawerMode>("view");
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

  const isSystemAdmin = React.useMemo(() => detectSystemAdmin(me), [me]);

  const filteredItems = React.useMemo(() => {
    return items.filter((item) => {
      const bySearch = matchesSearch(taskTitleOf(item), search);
      const kindValue = normalizeTaskKind(item?.task_kind);
      const byTaskKind = taskKind === "all" ? true : kindValue === taskKind;
      return bySearch && byTaskKind;
    });
  }, [items, search, taskKind]);

  function resetDrawerState() {
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
  }

  const redirectToLogin = React.useCallback(() => {
    logout();
    router.replace("/login");
  }, [router]);

  const closeDrawer = React.useCallback(() => {
    if (saving) return;
    resetDrawerState();
  }, [saving]);

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
    async (nextOffset?: number) => {
      setListLoading(true);
      setPageError(null);

      try {
        const qOffset = typeof nextOffset === "number" ? nextOffset : offset;

        const body = await apiFetchJson<any>("/tasks", {
          query: {
            limit: LIST_LIMIT,
            offset: qOffset,
            status_filter: tab,
          } as any,
        });

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

        const st = e?.status;
        const msg = normalizeMsg(e?.message || "Не удалось загрузить список задач");
        setItems([]);
        setTotal(0);
        setPageError(st ? `(${st}) ${msg}` : msg);
      } finally {
        setListLoading(false);
      }
    },
    [offset, tab, selectedId, drawerMode, redirectToLogin],
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

  React.useEffect(() => {
    void (async () => {
      if (!isAuthed()) {
        router.replace("/login");
        return;
      }

      try {
        const meBody = await apiAuthMe();
        setMe(meBody as MeInfo);
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
    if (!canEditTask(task, isSystemAdmin)) return;

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
      await apiFetchJson(`/tasks/${selectedId}`, {
        method: "PATCH",
        body: {
          title,
          description: values.description.trim() || null,
          source_note: values.source_note.trim() || null,
          due_date: values.due_date.trim() || null,
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

  const drawerSubtitle = drawerMode === "create" ? "Задачи" : "Должности процесса";

  const selectedAllowed = React.useMemo(() => allowedActionsOf(selectedItem), [selectedItem]);
  const selectedStatus = React.useMemo(() => statusTextOf(selectedItem), [selectedItem]);
  const selectedEditable = React.useMemo(
    () => canEditTask(selectedItem, isSystemAdmin),
    [selectedItem, isSystemAdmin],
  );

  const selectedReportUiState = React.useMemo(
    () => computeReportUiState(selectedItem),
    [selectedItem],
  );

  return (
    <div className="bg-[#04070f] text-zinc-100">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
        <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-[#050816]">
          <div className="border-b border-zinc-800 px-4 py-3">
            <h1 className="text-xl font-semibold text-zinc-100">Задачи</h1>
          </div>

          <div className="border-b border-zinc-800 px-4 py-2.5">
            <div className="flex flex-col gap-2 xl:flex-row xl:items-center">
              <div className="flex-1">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Поиск по названию задачи"
                  className="h-9 w-full rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                />
              </div>

              <select
                value={taskKind}
                onChange={(e) => setTaskKind(e.target.value as TaskKindFilter)}
                className="h-9 min-w-[220px] rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-100 outline-none transition focus:border-zinc-600"
              >
                {TASK_KIND_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value} className="bg-zinc-950 text-zinc-100">
                    {opt.label}
                  </option>
                ))}
              </select>

              <div className="flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-950/40 p-1">
                {(["active", "done", "rejected"] as StatusTab[]).map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => {
                      setTab(v);
                      setOffset(0);
                    }}
                    className={[
                      "rounded-md px-3 py-1.5 text-[12px] transition",
                      tab === v ? "bg-zinc-900 text-zinc-100" : "text-zinc-300 hover:bg-zinc-900/60",
                    ].join(" ")}
                  >
                    {tabRu(v)}
                  </button>
                ))}
              </div>

              <button
                type="button"
                onClick={() => void loadItems()}
                className="h-9 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-200 transition hover:bg-zinc-900/60"
              >
                Обновить
              </button>

              {canCreateManualTask ? (
                <button
                  type="button"
                  onClick={openCreate}
                  disabled={!currentPeriodId || manualRolesLoading}
                  className="h-9 rounded-lg bg-blue-600 px-4 text-[13px] font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Создать
                </button>
              ) : null}
            </div>
          </div>

          <div className="px-4 py-3">
            {!!pageError && (
              <div className="mb-3 rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
                {pageError}
              </div>
            )}

            <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-400">
              <div>
                Всего: {total} · Показано: {filteredItems.length}
                {listLoading ? <span className="ml-2">· загрузка…</span> : null}
                {manualRolesLoading ? <span className="ml-2">· роли…</span> : null}
              </div>

              <div className="text-zinc-500">
                Период: {currentPeriodName ? `${currentPeriodName} (#${currentPeriodId})` : `#${currentPeriodId}`}
              </div>
            </div>

            <div className="overflow-hidden rounded-xl border border-zinc-800">
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                  <thead>
                    <tr className="bg-white/[0.03] text-left">
                      <th className="w-[72px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        ID
                      </th>
                      <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Название
                      </th>
                      <th className="w-[170px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Статус
                      </th>
                      <th className="w-[120px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Тип
                      </th>
                      <th className="w-[140px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Дедлайн
                      </th>
                      <th className="w-[220px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-400">
                        Действия
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {listLoading ? (
                      <tr>
                        <td colSpan={6} className="px-3 py-2.5 text-[13px] text-zinc-400">
                          Загрузка...
                        </td>
                      </tr>
                    ) : filteredItems.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="px-3 py-2.5 text-[13px] text-zinc-500">
                          Записи не найдены.
                        </td>
                      </tr>
                    ) : (
                      filteredItems.map((item) => {
                        const id = taskIdOf(item);
                        const editable = canEditTask(item, isSystemAdmin);

                        return (
                          <tr
                            key={id}
                            className="cursor-pointer border-t border-zinc-800 align-middle transition hover:bg-white/[0.02]"
                            onClick={() => openView(item)}
                          >
                            <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-100">{id}</td>
                            <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-100">
                              {taskTitleOf(item)}
                            </td>
                            <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-400">
                              {statusTextOf(item)}
                            </td>
                            <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-400">
                              {taskKindLabelOf(item)}
                            </td>
                            <td className="px-3 py-1.5 text-[13px] leading-4 text-zinc-400">
                              {formatDeadline(item)}
                            </td>
                            <td className="px-3 py-1.5">
                              <div className="flex items-center gap-1.5">
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    openView(item);
                                  }}
                                  className="rounded-md border border-zinc-800 bg-zinc-950/40 px-2.5 py-1 text-[12px] leading-4 text-zinc-100 transition hover:bg-zinc-900/60"
                                >
                                  Открыть
                                </button>

                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    openEdit(item);
                                  }}
                                  disabled={!editable}
                                  title={editButtonTitle(item, isSystemAdmin)}
                                  className="rounded-md border border-zinc-800 bg-zinc-950/40 px-2.5 py-1 text-[12px] leading-4 text-zinc-100 transition hover:bg-zinc-900/60 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                  Изменить
                                </button>

                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    void handleDelete(item, false);
                                  }}
                                  className="rounded-md border border-red-800 bg-transparent px-2.5 py-1 text-[12px] leading-4 text-red-300 transition hover:bg-red-950/30"
                                >
                                  Удалить
                                </button>
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

            <div className="mt-3 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setOffset((v) => Math.max(0, v - LIST_LIMIT))}
                className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-[13px] text-zinc-200 transition hover:bg-zinc-900/60 disabled:opacity-60"
                disabled={listLoading || offset <= 0}
              >
                Назад
              </button>

              <button
                type="button"
                onClick={() => setOffset((v) => v + LIST_LIMIT)}
                className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-[13px] text-zinc-200 transition hover:bg-zinc-900/60 disabled:opacity-60"
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
                void loadItems(0);
                }}
            />
            </div>
            
        ) : drawerMode === "edit" ? (
          drawerLoading && !selectedItem ? (
            <div className="px-6 py-5 text-sm text-zinc-400">Загрузка...</div>
          ) : (
            <TaskEditForm
              mode="edit"
              initialValues={currentEditValues}
              saving={saving}
              error={drawerError}
              onCancel={closeDrawer}
              onSubmit={handleSaveEdit}
            />
          )
        ) : (
          <div className="flex h-full flex-col bg-[#050816] text-zinc-100">
            <div className="flex-1 overflow-y-auto px-6 py-5">
              {drawerLoading && !selectedItem ? (
                <div className="text-sm text-zinc-400">Загрузка...</div>
              ) : !selectedItem ? (
                <div className="text-sm text-zinc-500">Задача не выбрана.</div>
              ) : (
                <div className="space-y-5">
                  {!!drawerError && (
                    <div className="rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
                      {drawerError}
                    </div>
                  )}

                  {!!uiNotice && (
                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/40 px-4 py-3 text-sm text-zinc-200">
                      {uiNotice}
                    </div>
                  )}

                  <div className="flex flex-wrap items-center gap-2">
                    <div className="rounded-md border border-zinc-700 bg-zinc-950/40 px-2 py-1 text-xs text-zinc-200">
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
                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">ID</div>
                      <div className="mt-1 text-sm text-zinc-100">{taskIdOf(selectedItem)}</div>
                    </div>

                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">Дедлайн</div>
                      <div className="mt-1 text-sm text-zinc-100">{formatDeadline(selectedItem)}</div>
                    </div>

                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">Тип задачи</div>
                      <div className="mt-1 text-sm text-zinc-100">{taskKindLabelOf(selectedItem)}</div>
                    </div>

                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">Источник</div>
                      <div className="mt-1 text-sm text-zinc-100">
                        {String(selectedItem?.source_kind ?? "—")}
                      </div>
                    </div>
                  </div>

                  {String(selectedItem?.description ?? "").trim() ? (
                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">Описание</div>
                      <div className="mt-2 whitespace-pre-wrap text-sm text-zinc-100">
                        {String(selectedItem?.description ?? "").trim()}
                      </div>
                    </div>
                  ) : null}

                  {String(selectedItem?.source_note ?? "").trim() ? (
                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="text-xs text-zinc-500">Примечание</div>
                      <div className="mt-2 whitespace-pre-wrap text-sm text-zinc-100">
                        {String(selectedItem?.source_note ?? "").trim()}
                      </div>
                    </div>
                  ) : null}

                  <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                    <div className="mb-1 text-xs text-zinc-500">Доступные действия</div>
                    <div className="text-sm text-zinc-100">{actionsRu(selectedAllowed)}</div>
                  </div>

                  {String(selectedItem?.report_link ?? "").trim() ? (
                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                      <div className="mb-2 text-xs text-zinc-500">Отчёт</div>

                      {isHttpUrl(String(selectedItem?.report_link ?? "").trim()) ? (
                        <a
                          href={String(selectedItem?.report_link ?? "").trim()}
                          target="_blank"
                          rel="noreferrer"
                          className="break-all text-sm text-blue-400 underline"
                        >
                          Открыть отчёт
                        </a>
                      ) : (
                        <div className="space-y-2">
                          <div className="break-all text-sm text-zinc-200">
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
                              className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-900/60"
                            >
                              Скопировать путь
                            </button>

                            {isUncPath(String(selectedItem?.report_link ?? "").trim()) ||
                            isWindowsDrivePath(String(selectedItem?.report_link ?? "").trim()) ? (
                              <div className="text-xs text-zinc-500">
                                UNC/локальный путь не открывается браузером напрямую.
                              </div>
                            ) : (
                              <div className="text-xs text-zinc-500">Ссылка не является http(s).</div>
                            )}

                            {copyHint ? <div className="text-xs text-zinc-400">• {copyHint}</div> : null}
                          </div>
                        </div>
                      )}

                      {selectedItem?.report_submitted_at ? (
                        <div className="mt-3 text-xs text-zinc-400">
                          Отчёт отправлен:{" "}
                          <span className="text-zinc-200">{fmtDtRu(selectedItem?.report_submitted_at)}</span>
                        </div>
                      ) : null}

                      {selectedItem?.report_submitted_by ? (
                        <div className="text-xs text-zinc-400">
                          Отправил:{" "}
                          <span className="text-zinc-200">
                            {roleLabelOfReport(selectedItem, "submitted")}
                          </span>
                        </div>
                      ) : null}

                      {selectedItem?.report_approved_at ? (
                        <div className="mt-2 text-xs text-zinc-400">
                          Решение принято:{" "}
                          <span className="text-zinc-200">{fmtDtRu(selectedItem?.report_approved_at)}</span>
                        </div>
                      ) : null}

                      {selectedItem?.report_approved_by ? (
                        <div className="text-xs text-zinc-400">
                          Принял решение:{" "}
                          <span className="text-zinc-200">
                            {roleLabelOfReport(selectedItem, "approved")}
                          </span>
                        </div>
                      ) : null}

                      {String(selectedItem?.report_current_comment ?? "").trim() ? (
                        <div className="mt-2 text-xs text-zinc-400">
                          Комментарий:{" "}
                          <span className="text-zinc-200">
                            {String(selectedItem?.report_current_comment ?? "").trim()}
                          </span>
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {selectedAllowed.includes("report") ? (
                    <div className="flex flex-col gap-2">
                      <label className="text-sm font-medium text-zinc-200">Ссылка или путь на отчёт</label>
                      <input
                        value={reportLink}
                        onChange={(e) => setReportLink(e.target.value)}
                        placeholder="https://... или \\server\share\... или d:\..."
                        className="h-11 rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                      />
                    </div>
                  ) : null}

                  {selectedAllowed.length > 0 ? (
                    <div className="flex flex-col gap-2">
                      <label className="text-sm font-medium text-zinc-200">Причина / комментарий</label>
                      <textarea
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        rows={4}
                        placeholder="Комментарий для действия"
                        className="min-h-[96px] resize-y rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-3 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                      />
                    </div>
                  ) : null}
                </div>
              )}
            </div>

            {selectedItem ? (
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-zinc-800 px-6 py-4">
                <div className="text-xs text-zinc-500">{actionsRu(selectedAllowed)}</div>

                <div className="flex flex-wrap items-center gap-2">
                  {selectedEditable ? (
                    <button
                      type="button"
                      onClick={() => setDrawerMode("edit")}
                      disabled={saving || drawerLoading}
                      className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60 disabled:opacity-60"
                    >
                      Изменить
                    </button>
                  ) : null}

                  <button
                    type="button"
                    onClick={() => void handleDelete(selectedItem, false)}
                    disabled={saving || drawerLoading}
                    className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60 disabled:opacity-60"
                  >
                    Удалить
                  </button>

                  {isSystemAdmin ? (
                    <button
                      type="button"
                      onClick={() => void handleDelete(selectedItem, true)}
                      disabled={saving || drawerLoading}
                      className="rounded-lg border border-red-900/60 bg-red-950/20 px-4 py-2 text-sm text-red-200 transition hover:bg-red-950/40 disabled:opacity-60"
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
                      className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60 disabled:opacity-60"
                    >
                      {ACTION_RU.approve}
                    </button>
                  ) : null}

                  {selectedAllowed.includes("reject") ? (
                    <button
                      type="button"
                      onClick={() => void runAction("reject")}
                      disabled={saving || drawerLoading}
                      className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60 disabled:opacity-60"
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
                      className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60 disabled:opacity-60"
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