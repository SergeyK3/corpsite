// FILE: corpsite-ui/app/tasks/_components/CreateManualTaskModal.tsx
"use client";

import * as React from "react";
import { apiAuthMe, apiFetchJson } from "../../../lib/api";

export type ManualTaskRoleOption = {
  role_id: number;
  role_code?: string | null;
  role_name?: string | null;
  role_name_ru?: string | null;
};

type Props = {
  periodId: number;
  roleOptions: ManualTaskRoleOption[];
  onCreated?: () => void;
};

type AssignmentScope = "role" | "unit" | "group" | "dept";

function normalizeMsg(e: any): string {
  const badObjectString = "[object Object]";

  const direct = String(e?.message ?? "").trim();
  if (direct && direct !== badObjectString) return direct;

  const detail = e?.detail ?? e?.details?.detail ?? e?.response?.detail ?? e?.data?.detail;

  if (typeof detail === "string" && detail.trim() && detail.trim() !== badObjectString) {
    return detail.trim();
  }

  if (Array.isArray(detail)) {
    const joined = detail
      .map((x) => {
        if (typeof x === "string") return x;
        if (x && typeof x === "object") {
          const msg = String(x?.msg ?? x?.message ?? x?.detail ?? "").trim();
          const loc = Array.isArray(x?.loc) ? x.loc.join(" → ") : "";
          if (loc && msg) return `${loc}: ${msg}`;
          if (msg) return msg;
          return "";
        }
        return String(x ?? "").trim();
      })
      .filter(Boolean)
      .join("; ");

    if (joined) return joined;
  }

  if (detail && typeof detail === "object") {
    const msg = String(detail?.msg ?? detail?.message ?? detail?.detail ?? "").trim();
    if (msg && msg !== badObjectString) return msg;
  }

  return "Ошибка создания задачи";
}

function roleLabelOf(role: ManualTaskRoleOption): string {
  const name =
    String(role?.role_name_ru ?? "").trim() ||
    String(role?.role_name ?? "").trim() ||
    `role_id=${String(role?.role_id ?? "")}`;

  const code = String(role?.role_code ?? "").trim();
  return code ? `${name} (${code})` : name;
}

function extractCurrentUserId(me: any): number | null {
  const raw = me?.user_id ?? me?.id ?? me?.user?.user_id ?? me?.user?.id ?? null;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : null;
}

function addDays(date: Date, days: number): Date {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

function toDateInputValue(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function defaultDueDateValue(): string {
  return toDateInputValue(addDays(new Date(), 2));
}

const ASSIGNMENT_SCOPE_OPTIONS: Array<{ value: AssignmentScope; label: string }> = [
  { value: "role", label: "По роли" },
  { value: "unit", label: "По отделению" },
  { value: "group", label: "По группе" },
  { value: "dept", label: "По департаменту" },
];

export default function CreateManualTaskModal({ periodId, roleOptions, onCreated }: Props) {
  const [title, setTitle] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [executorRoleId, setExecutorRoleId] = React.useState<number | "">("");
  const [dueDate, setDueDate] = React.useState<string>(defaultDueDateValue());

  const [assignmentScope, setAssignmentScope] = React.useState<AssignmentScope>("role");
  const [requiresReport, setRequiresReport] = React.useState(true);
  const [requiresApproval, setRequiresApproval] = React.useState(true);

  const [sourceNote, setSourceNote] = React.useState("");
  const [currentUserId, setCurrentUserId] = React.useState<number | null>(null);

  const [loading, setLoading] = React.useState(false);
  const [bootstrapLoading, setBootstrapLoading] = React.useState(true);
  const [error, setError] = React.useState<string>("");
  const [success, setSuccess] = React.useState<string>("");

  const hasRoles = Array.isArray(roleOptions) && roleOptions.length > 0;

  React.useEffect(() => {
    let alive = true;

    void (async () => {
      try {
        const me = await apiAuthMe();
        if (!alive) return;
        setCurrentUserId(extractCurrentUserId(me));
      } catch {
        if (!alive) return;
        setCurrentUserId(null);
      } finally {
        if (alive) setBootstrapLoading(false);
      }
    })();

    return () => {
      alive = false;
    };
  }, []);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (loading || bootstrapLoading) return;

    setError("");
    setSuccess("");

    const trimmedTitle = title.trim();
    const trimmedDescription = description.trim();
    const trimmedSourceNote = sourceNote.trim();
    const trimmedDueDate = String(dueDate || "").trim();
    const roleId = Number(executorRoleId);

    if (!periodId || !Number.isFinite(Number(periodId)) || Number(periodId) <= 0) {
      setError("Не определён текущий период.");
      return;
    }

    if (!trimmedTitle) {
      setError("Заполните название задачи.");
      return;
    }

    if (!hasRoles) {
      setError("Нет доступных исполнителей для постановки разовой задачи.");
      return;
    }

    if (!Number.isFinite(roleId) || roleId <= 0) {
      setError("Выберите исполнителя.");
      return;
    }

    if (!trimmedDueDate || !/^\d{4}-\d{2}-\d{2}$/.test(trimmedDueDate)) {
      setError("Укажите корректную дату дедлайна.");
      return;
    }

    if (requiresApproval && (!currentUserId || currentUserId <= 0)) {
      setError("Не удалось определить согласующего по умолчанию.");
      return;
    }

    setLoading(true);

    try {
      const payload = {
        period_id: periodId,
        title: trimmedTitle,
        description: trimmedDescription || null,
        executor_role_id: roleId,
        assignment_scope: assignmentScope,
        requires_report: requiresReport,
        requires_approval: requiresApproval,
        approver_user_id: requiresApproval ? currentUserId : null,
        due_date: trimmedDueDate,
        due_at: `${trimmedDueDate}T00:00:00`,
        source_kind: "manual",
        source_note: trimmedSourceNote || null,
      };

      await apiFetchJson("/tasks/manual", {
        method: "POST",
        body: payload,
      });

      setTitle("");
      setDescription("");
      setExecutorRoleId("");
      setDueDate(defaultDueDateValue());
      setAssignmentScope("role");
      setRequiresReport(true);
      setRequiresApproval(true);
      setSourceNote("");
      setSuccess("Задача создана.");

      onCreated?.();
    } catch (e: any) {
      setError(normalizeMsg(e));
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex min-h-full flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 px-4 py-3 text-sm text-zinc-700 dark:text-zinc-300">
            <div>
              Текущий период: <span className="text-zinc-900 dark:text-zinc-50">#{periodId}</span>
            </div>
            <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              По умолчанию дедлайн ставится на 2 дня вперёд.
            </div>
          </div>

          {!!error && (
            <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
              {error}
            </div>
          )}

          {!!success && (
            <div className="rounded-xl border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/30 px-4 py-3 text-sm text-emerald-800 dark:text-emerald-200">
              {success}
            </div>
          )}

          {!hasRoles && (
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 px-4 py-3 text-sm text-zinc-600 dark:text-zinc-400">
              Для вашей роли сейчас нет доступных исполнителей, которым можно поставить разовую задачу.
            </div>
          )}

          <div className="flex flex-col gap-2">
            <label htmlFor="manual-task-title" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Название задачи <span className="text-red-400">*</span>
            </label>
            <input
              id="manual-task-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Например: Подготовить сводку по отделению"
              autoComplete="off"
              spellCheck={false}
              disabled={loading || bootstrapLoading}
              className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400 disabled:opacity-60"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="manual-task-description" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Описание
            </label>
            <textarea
              id="manual-task-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Описание задачи"
              rows={5}
              disabled={loading || bootstrapLoading}
              className="min-h-[120px] resize-y rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-3 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400 disabled:opacity-60"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="manual-task-due-date" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Дедлайн <span className="text-red-400">*</span>
            </label>
            <input
              id="manual-task-due-date"
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              disabled={loading || bootstrapLoading}
              style={{ colorScheme: "dark" }}
              className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400 disabled:opacity-60"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="manual-task-role" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Исполнитель <span className="text-red-400">*</span>
            </label>
            <select
              id="manual-task-role"
              value={executorRoleId}
              onChange={(e) => setExecutorRoleId(e.target.value ? Number(e.target.value) : "")}
              disabled={loading || bootstrapLoading || !hasRoles}
              className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400 disabled:opacity-60"
            >
              <option value="">Выберите роль исполнителя</option>
              {roleOptions.map((role) => (
                <option key={role.role_id} value={role.role_id} className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                  {roleLabelOf(role)}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="manual-task-scope" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Тип назначения
            </label>
            <select
              id="manual-task-scope"
              value={assignmentScope}
              onChange={(e) => setAssignmentScope(e.target.value as AssignmentScope)}
              disabled={loading || bootstrapLoading}
              className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400 disabled:opacity-60"
            >
              {ASSIGNMENT_SCOPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value} className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label className="flex items-center gap-3 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 px-4 py-3 text-sm text-zinc-800 dark:text-zinc-200">
              <input
                type="checkbox"
                checked={requiresReport}
                onChange={(e) => setRequiresReport(e.target.checked)}
                disabled={loading || bootstrapLoading}
                className="h-4 w-4"
              />
              <span>Требуется отчёт</span>
            </label>

            <label className="flex items-center gap-3 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 px-4 py-3 text-sm text-zinc-800 dark:text-zinc-200">
              <input
                type="checkbox"
                checked={requiresApproval}
                onChange={(e) => setRequiresApproval(e.target.checked)}
                disabled={loading || bootstrapLoading}
                className="h-4 w-4"
              />
              <span>Требуется согласование</span>
            </label>
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="manual-task-note" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Комментарий
            </label>
            <textarea
              id="manual-task-note"
              value={sourceNote}
              onChange={(e) => setSourceNote(e.target.value)}
              placeholder="Служебная пометка или основание постановки задачи"
              rows={4}
              disabled={loading || bootstrapLoading}
              className="min-h-[96px] resize-y rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-3 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400 disabled:opacity-60"
            />
          </div>
        </div>
      </div>

      <div className="mt-6 flex items-center justify-end gap-3 border-t border-zinc-200 dark:border-zinc-800 pt-4">
        <button
          type="submit"
          disabled={loading || bootstrapLoading || !hasRoles}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Создание..." : "Создать"}
        </button>
      </div>
    </form>
  );
}