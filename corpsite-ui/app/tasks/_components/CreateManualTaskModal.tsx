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

  async function handleSubmit() {
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
    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/20">
      <div className="max-h-[75vh] overflow-y-auto p-4">
        <div className="mb-4">
          <div className="text-lg font-semibold text-zinc-100">Создать разовую задачу</div>
          <div className="mt-1 text-xs text-zinc-500">
            Текущий период: <span className="text-zinc-300">#{periodId}</span>{" "}
            <span className="text-zinc-500">(недельный)</span>
          </div>
        </div>

        {error ? (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        {success ? (
          <div className="mb-4 rounded-xl border border-emerald-800 bg-emerald-950/30 px-3 py-2 text-sm text-emerald-200">
            {success}
          </div>
        ) : null}

        {!hasRoles ? (
          <div className="mb-4 rounded-xl border border-zinc-800 bg-zinc-950/30 px-3 py-2 text-sm text-zinc-400">
            Для вашей роли сейчас нет доступных исполнителей, которым можно поставить разовую задачу.
          </div>
        ) : null}

        <div className="grid grid-cols-1 gap-4">
          <div>
            <label className="block text-xs text-zinc-400">* Название новой задачи (обязательно)</label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none placeholder:text-zinc-500 italic"
              placeholder="Введите название новой задачи. Например, сделать сводку по отделению"
              disabled={loading || bootstrapLoading}
            />
          </div>

          <div>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="mt-1 min-h-[72px] w-full resize-y rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none placeholder:text-zinc-500"
              placeholder="Описание задачи"
              disabled={loading || bootstrapLoading}
            />
          </div>

          <div>
            <label className="block text-xs text-zinc-300">
              Дедлайн. По умолчанию: дата назначения + 2 дня. Изменить дату можно через значок календаря справа.
            </label>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="mt-1 w-full cursor-pointer rounded-md border border-zinc-700 bg-zinc-900 px-3 py-3 text-sm text-zinc-100 outline-none hover:border-zinc-500 focus:border-zinc-400"
              style={{ colorScheme: "dark" }}
              disabled={loading || bootstrapLoading}
              title="Нажмите на значок календаря справа, чтобы изменить дату дедлайна"
            />
          </div>

          <div>
            <select
              value={executorRoleId}
              onChange={(e) => setExecutorRoleId(e.target.value ? Number(e.target.value) : "")}
              className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
              disabled={loading || bootstrapLoading || !hasRoles}
            >
              <option value="">Выберите роль исполнителя</option>
              {roleOptions.map((role) => (
                <option key={role.role_id} value={role.role_id}>
                  {roleLabelOf(role)}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-zinc-400">Тип назначения</label>
            <select
              value={assignmentScope}
              onChange={(e) => setAssignmentScope(e.target.value as AssignmentScope)}
              className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
              disabled={loading || bootstrapLoading}
            >
              <option value="role">role</option>
              <option value="unit">unit</option>
              <option value="group">group</option>
              <option value="dept">dept</option>
            </select>
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <label className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-sm text-zinc-200">
              <input
                type="checkbox"
                checked={requiresReport}
                onChange={(e) => setRequiresReport(e.target.checked)}
                disabled={loading || bootstrapLoading}
              />
              <span>Требуется отчёт</span>
            </label>

            <label className="flex items-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-sm text-zinc-200">
              <input
                type="checkbox"
                checked={requiresApproval}
                onChange={(e) => setRequiresApproval(e.target.checked)}
                disabled={loading || bootstrapLoading}
              />
              <span>Требуется согласование</span>
            </label>
          </div>

          <div>
            <label className="block text-xs text-zinc-400">Комментарий</label>
            <textarea
              value={sourceNote}
              onChange={(e) => setSourceNote(e.target.value)}
              className="mt-1 min-h-[90px] w-full resize-y rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none placeholder:text-zinc-500"
              placeholder="Служебная пометка / основание постановки задачи"
              disabled={loading || bootstrapLoading}
            />
          </div>
        </div>
      </div>

      <div className="sticky bottom-0 flex flex-wrap gap-2 rounded-b-2xl border-t border-zinc-800 bg-zinc-950/95 px-4 py-3">
        <button
          onClick={handleSubmit}
          disabled={loading || bootstrapLoading || !hasRoles}
          className="rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
        >
          {loading ? "Создание..." : "Создать задачу"}
        </button>
      </div>
    </div>
  );
}