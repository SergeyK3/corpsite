// FILE: corpsite-ui/app/regular-tasks/page.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import {
  apiActivateRegularTask,
  apiCreateRegularTask,
  apiDeactivateRegularTask,
  apiGetRegularTask,
  apiGetRegularTasks,
  apiPatchRegularTask,
} from "@/lib/api";
import type { RegularTask, RegularTasksListResponse } from "@/lib/types";

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

function rtIdOf(t: any): number {
  return Number(t?.regular_task_id ?? t?.id ?? 0);
}

function rtTitleOf(t: any): string {
  const id = rtIdOf(t);
  const title = String(t?.title ?? "").trim();
  return title || (id > 0 ? `Шаблон #${id}` : "Шаблон");
}

function rtCodeOf(t: any): string {
  const code = String(t?.code ?? "").trim();
  return code || "—";
}

function rtScheduleOf(t: any): string {
  const st = String(t?.schedule_type ?? "").trim();
  return st || "—";
}

function rtActiveOf(t: any): boolean {
  return !!t?.is_active;
}

function safeJsonParse(v: string): any {
  const s = (v ?? "").trim();
  if (!s) return {};
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

function safeInt(v: any): number | null {
  const n = Number(v);
  if (!Number.isFinite(n)) return null;
  const i = Math.trunc(n);
  return i === n ? i : i;
}

export default function RegularTasksPage() {
  const [userId, setUserIdState] = useState<number>(1);

  const [status, setStatus] = useState<"active" | "inactive" | "all">("active");
  const [q, setQ] = useState<string>("");

  const [list, setList] = useState<RegularTasksListResponse>({ total: 0, limit: 50, offset: 0, items: [] });
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [item, setItem] = useState<RegularTask | null>(null);
  const [itemLoading, setItemLoading] = useState(false);
  const [itemError, setItemError] = useState<string | null>(null);

  // --- Create form
  const [cTitle, setCTitle] = useState<string>("Ежедневный контроль");
  const [cCode, setCCode] = useState<string>("daily-check");
  const [cExecutorRoleId, setCExecutorRoleId] = useState<string>("1");
  const [cScheduleType, setCScheduleType] = useState<string>("DAILY");
  const [cScheduleParams, setCScheduleParams] = useState<string>(`{"hour":10,"minute":0}`);
  const [cCreateOffsetDays, setCCreateOffsetDays] = useState<string>("0");
  const [cDueOffsetDays, setCDueOffsetDays] = useState<string>("0");

  // --- Edit form (patch)
  const [pTitle, setPTitle] = useState<string>("");
  const [pCode, setPCode] = useState<string>("");
  const [pExecutorRoleId, setPExecutorRoleId] = useState<string>("");
  const [pScheduleType, setPScheduleType] = useState<string>("");
  const [pScheduleParams, setPScheduleParams] = useState<string>("{}");
  const [pCreateOffsetDays, setPCreateOffsetDays] = useState<string>("0");
  const [pDueOffsetDays, setPDueOffsetDays] = useState<string>("0");

  const selectedFromList = useMemo(() => {
    if (!selectedId) return null;
    return (list.items as any[]).find((x) => rtIdOf(x) === selectedId) ?? null;
  }, [list.items, selectedId]);

  function fillPatchFormFrom(rt: any) {
    setPTitle(String(rt?.title ?? ""));
    setPCode(String(rt?.code ?? ""));
    setPExecutorRoleId(rt?.executor_role_id == null ? "" : String(rt.executor_role_id));
    setPScheduleType(String(rt?.schedule_type ?? ""));
    setPScheduleParams(JSON.stringify(rt?.schedule_params ?? {}, null, 2));
    setPCreateOffsetDays(String(rt?.create_offset_days ?? 0));
    setPDueOffsetDays(String(rt?.due_offset_days ?? 0));
  }

  async function reloadList(uid?: number) {
    const devUserId = uid ?? userId;
    setListLoading(true);
    setListError(null);
    try {
      const data = await apiGetRegularTasks({
        devUserId,
        status,
        q: q.trim() ? q.trim() : undefined,
        limit: 50,
        offset: 0,
      });
      setList(data);

      if (selectedId && !data.items.some((x: any) => rtIdOf(x) === selectedId)) {
        setSelectedId(null);
        setItem(null);
      }
    } catch (e: any) {
      const st = e?.status;
      const msg = e?.message || "Failed to fetch regular tasks";
      setList({ total: 0, limit: 50, offset: 0, items: [] });
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
      const data = await apiGetRegularTask({ devUserId, regularTaskId: id });
      setItem(data);
      fillPatchFormFrom(data);
    } catch (e: any) {
      const st = e?.status;
      const msg = e?.message || "Failed to fetch regular task";
      setItem(null);
      setItemError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setItemLoading(false);
    }
  }

  async function onCreate() {
    setItemError(null);
    setItemLoading(true);

    const scheduleParamsObj = safeJsonParse(cScheduleParams);
    if (scheduleParamsObj === null) {
      setItemLoading(false);
      setItemError("Create: schedule_params is not valid JSON.");
      return;
    }

    const executorRoleId = safeInt(cExecutorRoleId);
    const createOffset = safeInt(cCreateOffsetDays);
    const dueOffset = safeInt(cDueOffsetDays);

    const payload: Record<string, any> = {
      title: cTitle.trim(),
      code: cCode.trim() ? cCode.trim() : null,
      executor_role_id: executorRoleId,
      schedule_type: cScheduleType.trim() ? cScheduleType.trim() : null,
      schedule_params: scheduleParamsObj ?? {},
      create_offset_days: createOffset ?? 0,
      due_offset_days: dueOffset ?? 0,
    };

    try {
      const created = await apiCreateRegularTask({ devUserId: userId, payload });
      await reloadList(userId);
      const newId = rtIdOf(created);
      if (newId > 0) {
        setSelectedId(newId);
        await reloadItem(newId, userId);
      }
    } catch (e: any) {
      const st = e?.status;
      const msg = e?.message || "Create failed";
      setItemError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setItemLoading(false);
    }
  }

  async function onPatch() {
    if (!selectedId) return;

    setItemError(null);
    setItemLoading(true);

    const scheduleParamsObj = safeJsonParse(pScheduleParams);
    if (scheduleParamsObj === null) {
      setItemLoading(false);
      setItemError("Patch: schedule_params is not valid JSON.");
      return;
    }

    const executorRoleId = pExecutorRoleId.trim() ? safeInt(pExecutorRoleId) : null;
    const createOffset = safeInt(pCreateOffsetDays);
    const dueOffset = safeInt(pDueOffsetDays);

    const payload: Record<string, any> = {
      title: pTitle.trim(),
      code: pCode.trim() ? pCode.trim() : null,
      executor_role_id: executorRoleId,
      schedule_type: pScheduleType.trim() ? pScheduleType.trim() : null,
      schedule_params: scheduleParamsObj ?? {},
      create_offset_days: createOffset ?? 0,
      due_offset_days: dueOffset ?? 0,
    };

    try {
      await apiPatchRegularTask({ devUserId: userId, regularTaskId: selectedId, payload });
      await Promise.all([reloadItem(selectedId, userId), reloadList(userId)]);
    } catch (e: any) {
      const st = e?.status;
      const msg = e?.message || "Patch failed";
      setItemError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setItemLoading(false);
    }
  }

  async function onToggleActive(makeActive: boolean) {
    if (!selectedId) return;
    setItemError(null);
    setItemLoading(true);
    try {
      if (makeActive) {
        await apiActivateRegularTask({ devUserId: userId, regularTaskId: selectedId });
      } else {
        await apiDeactivateRegularTask({ devUserId: userId, regularTaskId: selectedId });
      }
      await Promise.all([reloadItem(selectedId, userId), reloadList(userId)]);
    } catch (e: any) {
      const st = e?.status;
      const msg = e?.message || "Toggle failed";
      setItemError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setItemLoading(false);
    }
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

  const active = rtActiveOf(item ?? selectedFromList);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-6xl px-4 py-6">
        <div className="flex items-center justify-between gap-4">
          <div className="text-xl font-semibold">Corpsite / Regular tasks</div>

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
              <div className="text-sm uppercase tracking-wide text-zinc-300">Шаблоны</div>

              <button
                onClick={() => void reloadList(userId)}
                className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs hover:bg-zinc-800"
                disabled={listLoading}
              >
                Refresh
              </button>
            </div>

            <div className="mb-3 grid grid-cols-1 gap-2 md:grid-cols-2">
              <div>
                <label className="block text-xs text-zinc-400">Status</label>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value as any)}
                  className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                >
                  <option value="active">active</option>
                  <option value="inactive">inactive</option>
                  <option value="all">all</option>
                </select>
              </div>

              <div>
                <label className="block text-xs text-zinc-400">Search</label>
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                  placeholder="q..."
                />
              </div>

              <div className="md:col-span-2">
                <button
                  onClick={() => void reloadList(userId)}
                  className="w-full rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800"
                  disabled={listLoading}
                >
                  Apply filters
                </button>
              </div>
            </div>

            {listError ? <div className="mb-3 text-sm text-red-400">Ошибка списка: {listError}</div> : null}
            {listLoading ? <div className="text-sm text-zinc-400">Загрузка…</div> : null}

            <div className="mb-3 text-xs text-zinc-500">
              total: <span className="text-zinc-200">{list.total}</span>
            </div>

            <div className="space-y-2">
              {(list.items as any[]).map((t) => {
                const id = rtIdOf(t);
                const isSel = selectedId === id;
                const isActive = rtActiveOf(t);

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
                      <div className="font-medium">{rtTitleOf(t)}</div>
                      <div className={["text-xs", isActive ? "text-emerald-300" : "text-zinc-400"].join(" ")}>
                        {isActive ? "active" : "inactive"}
                      </div>
                    </div>

                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-500">
                      <span>#{id}</span>
                      <span>code: {rtCodeOf(t)}</span>
                      <span>schedule: {rtScheduleOf(t)}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* RIGHT: create + details */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm uppercase tracking-wide text-zinc-300">Создание / карточка</div>
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

            {/* Create */}
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
              <div className="mb-2 text-sm font-semibold">Создать шаблон</div>

              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                <div className="md:col-span-2">
                  <label className="block text-xs text-zinc-400">Title</label>
                  <input
                    value={cTitle}
                    onChange={(e) => setCTitle(e.target.value)}
                    className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs text-zinc-400">Code (unique, optional)</label>
                  <input
                    value={cCode}
                    onChange={(e) => setCCode(e.target.value)}
                    className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                    placeholder="daily-check"
                  />
                </div>

                <div>
                  <label className="block text-xs text-zinc-400">Executor role id</label>
                  <input
                    value={cExecutorRoleId}
                    onChange={(e) => setCExecutorRoleId(e.target.value)}
                    className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                    inputMode="numeric"
                  />
                </div>

                <div>
                  <label className="block text-xs text-zinc-400">Schedule type</label>
                  <input
                    value={cScheduleType}
                    onChange={(e) => setCScheduleType(e.target.value)}
                    className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                    placeholder="DAILY"
                  />
                </div>

                <div>
                  <label className="block text-xs text-zinc-400">Create offset days</label>
                  <input
                    value={cCreateOffsetDays}
                    onChange={(e) => setCCreateOffsetDays(e.target.value)}
                    className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                    inputMode="numeric"
                  />
                </div>

                <div>
                  <label className="block text-xs text-zinc-400">Due offset days</label>
                  <input
                    value={cDueOffsetDays}
                    onChange={(e) => setCDueOffsetDays(e.target.value)}
                    className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                    inputMode="numeric"
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="block text-xs text-zinc-400">Schedule params (JSON)</label>
                  <textarea
                    value={cScheduleParams}
                    onChange={(e) => setCScheduleParams(e.target.value)}
                    className="mt-1 w-full min-h-[90px] resize-y rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                    placeholder='{"hour":10,"minute":0}'
                  />
                </div>
              </div>

              <div className="mt-3">
                <button
                  onClick={() => void onCreate()}
                  className="w-full rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                  disabled={itemLoading || !cTitle.trim()}
                >
                  Create
                </button>
              </div>
            </div>

            {/* Details */}
            <div className="mt-4 rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
              {!selectedId ? (
                <div className="text-sm text-zinc-400">Выберите шаблон слева.</div>
              ) : (
                <>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-lg font-semibold">{rtTitleOf(item ?? selectedFromList)}</div>
                      <div className="mt-1 text-sm text-zinc-400">
                        #{selectedId} • code: <span className="text-zinc-200">{rtCodeOf(item ?? selectedFromList)}</span> • schedule:{" "}
                        <span className="text-zinc-200">{rtScheduleOf(item ?? selectedFromList)}</span>
                      </div>
                    </div>

                    <div className={["text-xs rounded-md border px-2 py-1", active ? "border-emerald-800 text-emerald-300" : "border-zinc-700 text-zinc-300"].join(" ")}>
                      {active ? "active" : "inactive"}
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      onClick={() => void onToggleActive(true)}
                      disabled={itemLoading || active}
                      className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                    >
                      Activate
                    </button>
                    <button
                      onClick={() => void onToggleActive(false)}
                      disabled={itemLoading || !active}
                      className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                    >
                      Deactivate
                    </button>
                  </div>

                  <div className="mt-4 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
                    <div className="mb-2 text-sm font-semibold">Редактировать (PATCH)</div>

                    <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <div className="md:col-span-2">
                        <label className="block text-xs text-zinc-400">Title</label>
                        <input
                          value={pTitle}
                          onChange={(e) => setPTitle(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                        />
                      </div>

                      <div>
                        <label className="block text-xs text-zinc-400">Code</label>
                        <input
                          value={pCode}
                          onChange={(e) => setPCode(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                        />
                      </div>

                      <div>
                        <label className="block text-xs text-zinc-400">Executor role id (nullable)</label>
                        <input
                          value={pExecutorRoleId}
                          onChange={(e) => setPExecutorRoleId(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                          placeholder="(empty => null)"
                          inputMode="numeric"
                        />
                      </div>

                      <div>
                        <label className="block text-xs text-zinc-400">Schedule type</label>
                        <input
                          value={pScheduleType}
                          onChange={(e) => setPScheduleType(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                        />
                      </div>

                      <div>
                        <label className="block text-xs text-zinc-400">Create offset days</label>
                        <input
                          value={pCreateOffsetDays}
                          onChange={(e) => setPCreateOffsetDays(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                          inputMode="numeric"
                        />
                      </div>

                      <div>
                        <label className="block text-xs text-zinc-400">Due offset days</label>
                        <input
                          value={pDueOffsetDays}
                          onChange={(e) => setPDueOffsetDays(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                          inputMode="numeric"
                        />
                      </div>

                      <div className="md:col-span-2">
                        <label className="block text-xs text-zinc-400">Schedule params (JSON)</label>
                        <textarea
                          value={pScheduleParams}
                          onChange={(e) => setPScheduleParams(e.target.value)}
                          className="mt-1 w-full min-h-[110px] resize-y rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                        />
                      </div>
                    </div>

                    <div className="mt-3">
                      <button
                        onClick={() => void onPatch()}
                        disabled={itemLoading || !pTitle.trim()}
                        className="w-full rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      >
                        Save (PATCH)
                      </button>
                    </div>

                    <div className="mt-2 text-xs text-zinc-500">
                      Примечание: JSON должен быть валидным. Пустой executor_role_id => null.
                    </div>
                  </div>

                  <details className="mt-3 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
                    <summary className="cursor-pointer text-sm text-zinc-300">Raw JSON</summary>
                    <pre className="mt-2 overflow-auto text-xs text-zinc-200">
                      {JSON.stringify(item ?? selectedFromList, null, 2)}
                    </pre>
                  </details>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
