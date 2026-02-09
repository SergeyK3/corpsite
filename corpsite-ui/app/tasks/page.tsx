// FILE: corpsite-ui/app/tasks/page.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGetTask, apiGetTasks, apiPostTaskAction } from "@/lib/api";
import type { AllowedAction, TaskAction, TaskDetails, TaskListItem } from "@/lib/types";

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

function taskTitleOf(t: any): string {
  const id = taskIdOf(t);
  const title = String(t?.title ?? "").trim();
  return title || (id > 0 ? `Задача #${id}` : "Задача");
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

function pickString(payload: Record<string, any>, keys: string[]): string {
  for (const k of keys) {
    const v = payload[k];
    if (typeof v === "string") {
      const s = v.trim();
      if (s) return s;
    }
  }
  return "";
}

export default function TasksPage() {
  const [userId, setUserIdState] = useState<number>(1);

  const [limit, setLimit] = useState<number>(50);
  const [offset, setOffset] = useState<number>(0);

  const [list, setList] = useState<TaskListItem[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [item, setItem] = useState<TaskDetails | null>(null);
  const [itemLoading, setItemLoading] = useState(false);
  const [itemError, setItemError] = useState<string | null>(null);

  // action form
  const [reportLink, setReportLink] = useState<string>("");
  const [comment, setComment] = useState<string>("");

  const selectedFromList = useMemo(() => {
    if (!selectedId) return null;
    return (list as any[]).find((x) => taskIdOf(x) === selectedId) ?? null;
  }, [list, selectedId]);

  const effectiveAllowed = useMemo(() => {
    const src: any = item ?? selectedFromList;
    return allowedActionsOf(src);
  }, [item, selectedFromList]);

  const effectiveStatus = useMemo(() => {
    const src: any = item ?? selectedFromList;
    return statusTextOf(src);
  }, [item, selectedFromList]);

  async function reloadList(uid?: number) {
    const devUserId = uid ?? userId;
    setListLoading(true);
    setListError(null);
    try {
      const data = await apiGetTasks({ devUserId, limit, offset });
      setList(data);

      if (selectedId && !data.some((x: any) => taskIdOf(x) === selectedId)) {
        setSelectedId(null);
        setItem(null);
      }
    } catch (e: any) {
      const st = e?.status;
      const msg = e?.message || "Failed to fetch tasks";
      setList([]);
      setSelectedId(null);
      setItem(null);
      setListError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setListLoading(false);
    }
  }

  async function reloadItem(id: number, uid?: number) {
    const devUserId = uid ?? userId;
    setItemLoading(true);
    setItemError(null);
    try {
      const data = await apiGetTask({ devUserId, taskId: id, includeArchived: true });
      setItem(data);
    } catch (e: any) {
      const st = e?.status;
      const msg = e?.message || "Failed to fetch task";
      setItem(null);
      setItemError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setItemLoading(false);
    }
  }

  async function runAction(action: TaskAction) {
    if (!selectedId) return;
    const devUserId = userId;

    setItemError(null);
    setItemLoading(true);

    try {
      if (action === "report") {
        const link = reportLink.trim();
        if (!link) {
          setItemError("Report: укажи report_link (ссылка на отчет).");
          return;
        }
        await apiPostTaskAction({
          devUserId,
          taskId: selectedId,
          action,
          payload: {
            report_link: link,
            current_comment: comment.trim() ? comment.trim() : undefined,
          },
        });
      } else if (action === "approve" || action === "reject") {
        await apiPostTaskAction({
          devUserId,
          taskId: selectedId,
          action,
          payload: {
            current_comment: comment.trim() ? comment.trim() : undefined,
          },
        });
      } else if (action === "archive") {
        await apiPostTaskAction({
          devUserId,
          taskId: selectedId,
          action,
        });
      }

      await Promise.all([reloadItem(selectedId, devUserId), reloadList(devUserId)]);
    } catch (e: any) {
      const st = e?.status;
      const msg = e?.message || "Action failed";
      setItemError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setItemLoading(false);
    }
  }

  function can(action: AllowedAction): boolean {
    return effectiveAllowed.includes(action);
  }

  useEffect(() => {
    const uid = getDevUserId();
    setUserIdState(uid);
    void reloadList(uid);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setItem(null);
      setItemError(null);
      return;
    }
    void reloadItem(selectedId, userId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, userId]);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-6xl px-4 py-6">
        <div className="flex items-center justify-between gap-4">
          <div className="text-xl font-semibold">Corpsite / Tasks</div>

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
                if (selectedId) void reloadItem(selectedId, userId);
                setItemError(null);
              }}
              className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800"
            >
              Apply
            </button>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* LEFT: list */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm uppercase tracking-wide text-zinc-300">Список задач</div>

              <button
                onClick={() => void reloadList(userId)}
                className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs hover:bg-zinc-800"
                disabled={listLoading}
              >
                Refresh
              </button>
            </div>

            <div className="mb-3 grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-zinc-400">limit</label>
                <input
                  value={String(limit)}
                  onChange={(e) => setLimit(Number(e.target.value || "0"))}
                  className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                  inputMode="numeric"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-400">offset</label>
                <input
                  value={String(offset)}
                  onChange={(e) => setOffset(Number(e.target.value || "0"))}
                  className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                  inputMode="numeric"
                />
              </div>

              <div className="col-span-2">
                <button
                  onClick={() => void reloadList(userId)}
                  className="w-full rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800"
                  disabled={listLoading}
                >
                  Apply paging
                </button>
              </div>
            </div>

            {listError ? <div className="mb-3 text-sm text-red-400">Ошибка списка: {listError}</div> : null}
            {listLoading ? <div className="text-sm text-zinc-400">Загрузка…</div> : null}

            <div className="space-y-2">
              {(list as any[]).map((t) => {
                const id = taskIdOf(t);
                const isSel = selectedId === id;
                const actions = allowedActionsOf(t);
                const st = statusTextOf(t);

                return (
                  <button
                    key={id}
                    onClick={() => setSelectedId(id)}
                    className={[
                      "w-full rounded-lg border px-3 py-2 text-left",
                      isSel ? "border-zinc-600 bg-zinc-900" : "border-zinc-800 bg-zinc-950/40 hover:bg-zinc-900/60",
                    ].join(" ")}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="font-medium">{taskTitleOf(t)}</div>
                      <div className="text-xs text-zinc-300">{st}</div>
                    </div>

                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-500">
                      <span>#{id}</span>
                      <span>allowed: {actions.length ? actions.join(", ") : "—"}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* RIGHT: details + actions */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm uppercase tracking-wide text-zinc-300">Карточка / действия</div>
              <button
                onClick={() => (selectedId ? void reloadItem(selectedId, userId) : null)}
                className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs hover:bg-zinc-800"
                disabled={!selectedId || itemLoading}
              >
                Refresh
              </button>
            </div>

            {itemError ? <div className="mb-3 text-sm text-red-400">Ошибка: {itemError}</div> : null}
            {itemLoading ? <div className="mb-3 text-sm text-zinc-400">Загрузка…</div> : null}

            {!selectedId ? (
              <div className="text-sm text-zinc-400">Выберите задачу слева.</div>
            ) : (
              <>
                <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-lg font-semibold">{taskTitleOf(item ?? selectedFromList)}</div>
                      <div className="mt-1 text-sm text-zinc-400">#{selectedId}</div>
                    </div>
                    <div className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-200">{effectiveStatus}</div>
                  </div>

                  <div className="mt-2 text-xs text-zinc-500">
                    allowed_actions: <span className="text-zinc-200">{effectiveAllowed.length ? effectiveAllowed.join(", ") : "—"}</span>
                  </div>

                  <div className="mt-3 grid grid-cols-1 gap-2">
                    <div>
                      <label className="block text-xs text-zinc-400">report_link (для report)</label>
                      <input
                        value={reportLink}
                        onChange={(e) => setReportLink(e.target.value)}
                        className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                        placeholder="https://..."
                      />
                    </div>

                    <div>
                      <label className="block text-xs text-zinc-400">current_comment (опционально)</label>
                      <textarea
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        className="mt-1 w-full min-h-[80px] resize-y rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                        placeholder="Комментарий..."
                      />
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      onClick={() => void runAction("report")}
                      disabled={itemLoading || !can("report")}
                      className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      title={can("report") ? "" : "report не разрешен для этой задачи"}
                    >
                      report
                    </button>

                    <button
                      onClick={() => void runAction("approve")}
                      disabled={itemLoading || !can("approve")}
                      className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      title={can("approve") ? "" : "approve не разрешен для этой задачи"}
                    >
                      approve
                    </button>

                    <button
                      onClick={() => void runAction("reject")}
                      disabled={itemLoading || !can("reject")}
                      className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      title={can("reject") ? "" : "reject не разрешен для этой задачи"}
                    >
                      reject
                    </button>

                    <button
                      onClick={() => {
                        if (!can("archive")) return;
                        const ok = window.confirm("Archive (DELETE) — точно?");
                        if (ok) void runAction("archive");
                      }}
                      disabled={itemLoading || !can("archive")}
                      className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      title={can("archive") ? "" : "archive не разрешен для этой задачи"}
                    >
                      archive
                    </button>
                  </div>
                </div>

                <details className="mt-3 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
                  <summary className="cursor-pointer text-sm text-zinc-300">Raw JSON</summary>
                  <pre className="mt-2 overflow-auto text-xs text-zinc-200">{JSON.stringify(item ?? selectedFromList, null, 2)}</pre>
                </details>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
