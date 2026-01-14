// corpsite-ui/app/tasks/page.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGetTask, apiGetTasks, apiPostTaskAction } from "@/lib/api";
import type { TaskAction, TaskActionPayload, TaskDetails, TaskListItem } from "@/lib/types";

const DEV_USER_ID_KEY = "corpsite.devUserId";

function getDevUserId(): number {
  if (typeof window === "undefined") return 1;
  const raw = window.localStorage.getItem(DEV_USER_ID_KEY);
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

function setDevUserId(v: number): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(DEV_USER_ID_KEY, String(v));
}

function taskIdOf(t: any): number {
  return Number(t?.task_id ?? t?.id ?? 0);
}

function titleOf(t: any): string {
  return String(t?.title ?? t?.name ?? `Task #${taskIdOf(t)}`);
}

function statusOf(t: any): string {
  return String(t?.status ?? t?.status_code ?? "—");
}

function allowedActionsOf(t: any): string[] {
  const v = t?.allowed_actions ?? t?.allowedActions ?? [];
  if (Array.isArray(v)) return v.map(String);
  if (typeof v === "string") return v.split(",").map((s) => s.trim()).filter(Boolean);
  return [];
}

export default function TasksPage() {
  const [userId, setUserIdState] = useState<number>(1);

  const [tasks, setTasks] = useState<TaskListItem[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);

  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);

  const [task, setTask] = useState<TaskDetails | null>(null);
  const [taskLoading, setTaskLoading] = useState(false);
  const [taskError, setTaskError] = useState<string | null>(null);

  // inputs for actions
  const [reportLink, setReportLink] = useState<string>("https://example.com/r");
  const [comment, setComment] = useState<string>("");

  const selectedFromList = useMemo(() => {
    if (!selectedTaskId) return null;
    return (tasks as any[]).find((t) => taskIdOf(t) === selectedTaskId) ?? null;
  }, [tasks, selectedTaskId]);

  async function reloadList(uid?: number) {
    const devUserId = uid ?? userId;
    setListLoading(true);
    setListError(null);
    try {
      const data = await apiGetTasks({ devUserId, limit: 50, offset: 0 });
      setTasks(data);

      // если выбранной задачи больше нет — сброс выбора
      if (selectedTaskId && !data.some((x: any) => taskIdOf(x) === selectedTaskId)) {
        setSelectedTaskId(null);
        setTask(null);
      }
    } catch (e: any) {
      const status = e?.status;
      const msg = e?.message || "Failed to fetch tasks";
      setTasks([]);
      setSelectedTaskId(null);
      setTask(null);
      setListError(status ? `(${status}) ${msg}` : msg);
    } finally {
      setListLoading(false);
    }
  }

  async function reloadTask(taskId: number, uid?: number) {
    const devUserId = uid ?? userId;
    setTaskLoading(true);
    setTaskError(null);
    try {
      const data = await apiGetTask({ devUserId, taskId, includeArchived: false });
      setTask(data);
    } catch (e: any) {
      const status = e?.status;
      const msg = e?.message || "Failed to fetch task";
      setTask(null);
      setTaskError(status ? `(${status}) ${msg}` : msg);
    } finally {
      setTaskLoading(false);
    }
  }

  async function runAction(action: TaskAction) {
    if (!selectedTaskId) return;

    const actions = allowedActionsOf(task ?? selectedFromList);
    if (!actions.includes(action)) {
      setTaskError(`Action "${action}" is not allowed for this task.`);
      return;
    }

    const payload: TaskActionPayload = {} as any;

    if (action === "report") {
      (payload as any).report_link = reportLink;
      if (comment.trim()) (payload as any).comment = comment.trim();
    } else {
      // approve/reject: обычно только comment
      if (comment.trim()) (payload as any).comment = comment.trim();
    }

    setTaskError(null);
    setTaskLoading(true);
    try {
      await apiPostTaskAction({
        devUserId: userId,
        taskId: selectedTaskId,
        action,
        payload: payload as any,
      });

      // после действия — обновляем карточку и список
      await Promise.all([reloadTask(selectedTaskId, userId), reloadList(userId)]);
      setComment("");
    } catch (e: any) {
      const status = e?.status;
      const msg = e?.message || "Action failed";
      setTaskError(status ? `(${status}) ${msg}` : msg);
    } finally {
      setTaskLoading(false);
    }
  }

  useEffect(() => {
    const uid = getDevUserId();
    setUserIdState(uid);
    void reloadList(uid);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // при смене выбранной задачи — грузим карточку
  useEffect(() => {
    if (!selectedTaskId) {
      setTask(null);
      setTaskError(null);
      return;
    }
    void reloadTask(selectedTaskId, userId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTaskId]);

  const allowed = allowedActionsOf(task ?? selectedFromList);
  const hasReport = allowed.includes("report");
  const hasApprove = allowed.includes("approve");
  const hasReject = allowed.includes("reject");

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-6xl px-4 py-6">
        <div className="flex items-center justify-between gap-4">
          <div className="text-xl font-semibold">Corpsite / ЛК задач</div>

          <div className="flex items-center gap-2">
            <div className="text-xs text-zinc-400">
              <div>Dev</div>
              <div>User ID</div>
            </div>

            <input
              value={String(userId)}
              onChange={(e) => setUserIdState(Number(e.target.value || "0"))}
              className="w-28 rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
              inputMode="numeric"
            />

            <button
              onClick={() => {
                setDevUserId(userId);
                void reloadList(userId);
                // при смене юзера логично сбросить выбор
                setSelectedTaskId(null);
                setTask(null);
                setTaskError(null);
              }}
              className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800"
            >
              Apply
            </button>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* LEFT: LIST */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm uppercase tracking-wide text-zinc-300">Все задачи</div>
              <button
                onClick={() => void reloadList(userId)}
                className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs hover:bg-zinc-800"
                disabled={listLoading}
              >
                Refresh
              </button>
            </div>

            {listError ? <div className="mb-3 text-sm text-red-400">Ошибка списка: {listError}</div> : null}

            {listLoading ? <div className="text-sm text-zinc-400">Загрузка…</div> : null}

            <div className="space-y-2">
              {(tasks as any[]).map((t) => {
                const id = taskIdOf(t);
                const active = selectedTaskId === id;
                return (
                  <button
                    key={id}
                    onClick={() => setSelectedTaskId(id)}
                    className={[
                      "w-full rounded-lg border px-3 py-2 text-left",
                      active
                        ? "border-zinc-600 bg-zinc-900"
                        : "border-zinc-800 bg-zinc-950/40 hover:bg-zinc-900/60",
                    ].join(" ")}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="font-medium">{titleOf(t)}</div>
                      <div className="text-xs text-zinc-400">{statusOf(t)}</div>
                    </div>
                    <div className="mt-1 text-xs text-zinc-500">#{id}</div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* RIGHT: DETAILS */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm uppercase tracking-wide text-zinc-300">Карточка</div>
              <button
                onClick={() => (selectedTaskId ? void reloadTask(selectedTaskId, userId) : null)}
                className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs hover:bg-zinc-800"
                disabled={!selectedTaskId || taskLoading}
              >
                Refresh
              </button>
            </div>

            {!selectedTaskId ? (
              <div className="text-sm text-zinc-400">Выберите задачу слева.</div>
            ) : (
              <>
                {taskError ? <div className="mb-3 text-sm text-red-400">Ошибка: {taskError}</div> : null}
                {taskLoading ? <div className="mb-3 text-sm text-zinc-400">Загрузка…</div> : null}

                <div className="space-y-3">
                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
                    <div className="text-lg font-semibold">{titleOf(task ?? selectedFromList)}</div>
                    <div className="mt-1 text-sm text-zinc-400">
                      Статус: <span className="text-zinc-200">{statusOf(task ?? selectedFromList)}</span> • #{selectedTaskId}
                    </div>

                    <div className="mt-2 text-xs text-zinc-400">
                      allowed_actions:{" "}
                      <span className="text-zinc-200">
                        {allowed.length ? allowed.join(", ") : "—"}
                      </span>
                    </div>
                  </div>

                  {/* ACTIONS */}
                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
                    <div className="mb-2 text-sm font-semibold">Действия</div>

                    {hasReport ? (
                      <>
                        <label className="block text-xs text-zinc-400">Report link</label>
                        <input
                          value={reportLink}
                          onChange={(e) => setReportLink(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                          placeholder="https://..."
                        />
                      </>
                    ) : null}

                    <label className="mt-3 block text-xs text-zinc-400">Комментарий</label>
                    <textarea
                      value={comment}
                      onChange={(e) => setComment(e.target.value)}
                      className="mt-1 w-full min-h-[84px] resize-y rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                      placeholder="Комментарий (опционально)"
                    />

                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        onClick={() => void runAction("report")}
                        disabled={!hasReport || taskLoading}
                        className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      >
                        Report
                      </button>
                      <button
                        onClick={() => void runAction("approve")}
                        disabled={!hasApprove || taskLoading}
                        className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => void runAction("reject")}
                        disabled={!hasReject || taskLoading}
                        className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      >
                        Reject
                      </button>
                    </div>

                    <div className="mt-2 text-xs text-zinc-500">
                      Примечание: кнопки появляются только если action присутствует в allowed_actions.
                    </div>
                  </div>

                  {/* RAW JSON (удобно на MVP) */}
                  <details className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
                    <summary className="cursor-pointer text-sm text-zinc-300">Raw JSON</summary>
                    <pre className="mt-2 overflow-auto text-xs text-zinc-200">
                      {JSON.stringify(task ?? selectedFromList, null, 2)}
                    </pre>
                  </details>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
