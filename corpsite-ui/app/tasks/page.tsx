// FILE: corpsite-ui/app/tasks/page.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import {
  apiAuthMe,
  apiGetTask,
  apiGetTasks,
  apiPostTaskAction,
  clearAccessToken,
  isAuthed,
} from "@/lib/api";
import type { AllowedAction, TaskAction, TaskListItem } from "@/lib/types";

const ACTION_RU: Record<string, string> = {
  report: "Отправить отчёт",
  approve: "Согласовать",
  reject: "Отклонить",
  archive: "В архив",
};

type MeInfo = {
  user_id?: number;
  role_id?: number;
  role_name_ru?: string;
  role_name?: string;
  unit_id?: number | null;
  full_name?: string;
  login?: string;
};

function actionsRu(actions: AllowedAction[] | undefined | null): string {
  if (!actions || actions.length === 0) return "—";
  return actions.map((a) => ACTION_RU[String(a)] ?? String(a)).join(" / ");
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

function normalizeMsg(msg: string): string {
  const s = String(msg || "").trim();
  return s || "Ошибка запроса";
}

function isUnauthorized(e: any): boolean {
  const st = Number(e?.status ?? 0);
  return st === 401;
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

export default function TasksPage() {
  const router = useRouter();

  const [me, setMe] = useState<MeInfo | null>(null);
  const [myRoleId, setMyRoleId] = useState<number | null>(null);

  const [limit, setLimit] = useState<number>(50);
  const [offset, setOffset] = useState<number>(0);

  const [list, setList] = useState<TaskListItem[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [item, setItem] = useState<any | null>(null);
  const [itemLoading, setItemLoading] = useState(false);
  const [itemError, setItemError] = useState<string | null>(null);

  const [reportLink, setReportLink] = useState<string>("");
  const [reason, setReason] = useState<string>("");

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

  function can(action: AllowedAction): boolean {
    return effectiveAllowed.includes(action);
  }

  function redirectToLogin() {
    clearAccessToken();
    router.push("/login");
  }

  async function reloadList(roleId: number, nextOffset?: number) {
    setListLoading(true);
    setListError(null);

    try {
      const data = await apiGetTasks({
        limit,
        offset: typeof nextOffset === "number" ? nextOffset : offset,
        executor_role_id: roleId,
      } as any);

      setList(data);

      if (selectedId && !data.some((x: any) => taskIdOf(x) === selectedId)) {
        setSelectedId(null);
        setItem(null);
      }
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      const st = e?.status;
      const msg = normalizeMsg(e?.message || "Не удалось загрузить список задач");
      setList([]);
      setSelectedId(null);
      setItem(null);
      setListError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setListLoading(false);
    }
  }

  async function reloadItem(id: number) {
    setItemLoading(true);
    setItemError(null);

    try {
      const data = await apiGetTask({ taskId: id, includeArchived: true });
      setItem(data);
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      const st = e?.status;
      const msg = normalizeMsg(e?.message || "Не удалось загрузить задачу");
      setItem(null);
      setItemError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setItemLoading(false);
    }
  }

  async function runAction(action: TaskAction) {
    if (!selectedId) return;

    setItemError(null);
    setItemLoading(true);

    try {
      if (action === "report") {
        const link = reportLink.trim();
        if (!link) {
          setItemError("Отчёт: укажите ссылку.");
          return;
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
      } else if (action === "approve" || action === "reject" || action === "archive") {
        await apiPostTaskAction({
          taskId: selectedId,
          action,
          payload: reason.trim() ? ({ reason: reason.trim() as any } as any) : undefined,
        });
      }

      await Promise.all([reloadItem(selectedId), myRoleId ? reloadList(myRoleId) : Promise.resolve()]);
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      const st = e?.status;
      const msg = normalizeMsg(e?.message || "Не удалось выполнить действие");
      setItemError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setItemLoading(false);
    }
  }

  useEffect(() => {
    (async () => {
      if (!isAuthed()) {
        router.push("/login");
        return;
      }

      let meData: any;
      try {
        meData = await apiAuthMe();
      } catch (e: any) {
        if (isUnauthorized(e)) {
          redirectToLogin();
          return;
        }
        setListError(normalizeMsg(e?.message || "Ошибка авторизации"));
        return;
      }

      const roleId = Number(meData?.role_id ?? 0);
      setMe(meData as MeInfo);

      if (roleId > 0) {
        setMyRoleId(roleId);
        await reloadList(roleId, 0);
        setOffset(0);
      } else {
        setMyRoleId(null);
        setListError("Не удалось определить роль пользователя (/me).");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!myRoleId) return;
    void reloadList(myRoleId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [myRoleId, limit, offset]);

  useEffect(() => {
    if (!selectedId) {
      setItem(null);
      setItemError(null);
      return;
    }
    void reloadItem(selectedId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  const grouped = useMemo(() => {
    const m = new Map<string, any[]>();
    for (const t of list as any[]) {
      const key = statusTextOf(t) || "—";
      if (!m.has(key)) m.set(key, []);
      m.get(key)!.push(t);
    }

    for (const arr of m.values()) {
      arr.sort((a, b) => {
        const daRaw = a?.due_at ?? a?.due_date ?? a?.deadline ?? null;
        const dbRaw = b?.due_at ?? b?.due_date ?? b?.deadline ?? null;
        const da = daRaw ? new Date(String(daRaw)).getTime() : Number.POSITIVE_INFINITY;
        const db = dbRaw ? new Date(String(dbRaw)).getTime() : Number.POSITIVE_INFINITY;
        if (da !== db) return da - db;
        return taskIdOf(a) - taskIdOf(b);
      });
    }

    const keys = Array.from(m.keys());
    keys.sort((a, b) => a.localeCompare(b, "ru"));
    return { map: m, keys };
  }, [list]);

  const selectedTitle = taskTitleOf(item ?? selectedFromList);
  const selectedDeadline = selectedId ? formatDeadline(item ?? selectedFromList) : "—";

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm text-zinc-400">
          Показано: <span className="text-zinc-200">{list.length}</span>
          {listLoading ? <span className="ml-2">• загрузка…</span> : null}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => void (myRoleId ? reloadList(myRoleId) : Promise.resolve())}
            className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
            disabled={listLoading || !myRoleId}
          >
            Обновить
          </button>

          {/* оставляю limit/offset как тех.параметры, позже уберём полностью */}
          <input
            value={String(limit)}
            onChange={(e) => setLimit(Number(e.target.value || "0"))}
            className="w-20 rounded-md border border-zinc-800 bg-zinc-950/40 px-2 py-2 text-sm text-zinc-200 outline-none"
            inputMode="numeric"
            title="limit"
          />
        </div>
      </div>

      {listError ? (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {listError}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* LEFT: grouped list */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-950/20 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-zinc-100">Список</div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setOffset((v) => Math.max(0, v - limit))}
                className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                disabled={listLoading || offset <= 0}
                title="Предыдущая страница"
              >
                Назад
              </button>
              <button
                onClick={() => setOffset((v) => v + limit)}
                className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                disabled={listLoading || list.length < limit}
                title="Следующая страница"
              >
                Далее
              </button>
            </div>
          </div>

          {grouped.keys.length === 0 && !listLoading ? (
            <div className="text-sm text-zinc-400">Задач нет.</div>
          ) : (
            <div className="space-y-3">
              {grouped.keys.map((k) => {
                const items = grouped.map.get(k) ?? [];
                return (
                  <details key={k} open className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-3">
                    <summary className="cursor-pointer select-none text-sm text-zinc-200">
                      {k} <span className="text-zinc-500">({items.length})</span>
                    </summary>

                    <div className="mt-3 space-y-2">
                      {items.map((t) => {
                        const id = taskIdOf(t);
                        const isSel = selectedId === id;
                        const deadline = formatDeadline(t);
                        const actions = allowedActionsOf(t);

                        return (
                          <button
                            key={id}
                            onClick={() => setSelectedId(id)}
                            className={[
                              "w-full rounded-lg border px-3 py-2 text-left",
                              isSel
                                ? "border-zinc-600 bg-zinc-900"
                                : "border-zinc-800 bg-zinc-950/40 hover:bg-zinc-900/60",
                            ].join(" ")}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="font-medium text-zinc-100">{taskTitleOf(t)}</div>
                              <div className="text-xs text-zinc-400">Дедлайн: {deadline}</div>
                            </div>

                            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-500">
                              <span>№{id}</span>
                              <span>доступно: {actionsRu(actions)}</span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </details>
                );
              })}
            </div>
          )}
        </div>

        {/* RIGHT: details + actions */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-950/20 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-zinc-100">Карточка</div>

            <button
              onClick={() => (selectedId ? void reloadItem(selectedId) : null)}
              className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
              disabled={!selectedId || itemLoading}
            >
              Обновить
            </button>
          </div>

          {itemError ? (
            <div className="mb-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {itemError}
            </div>
          ) : null}

          {!selectedId ? (
            <div className="text-sm text-zinc-400">Выберите задачу слева.</div>
          ) : (
            <>
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/30 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-lg font-semibold text-zinc-100">{selectedTitle}</div>
                    <div className="mt-1 text-sm text-zinc-400">№{selectedId}</div>
                  </div>
                  <div className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-200">
                    {effectiveStatus}
                  </div>
                </div>

                <div className="mt-2 text-xs text-zinc-500">
                  Дедлайн: <span className="text-zinc-200">{selectedDeadline}</span>
                </div>

                <div className="mt-2 text-xs text-zinc-500">
                  Доступные действия: <span className="text-zinc-200">{actionsRu(effectiveAllowed)}</span>
                </div>

                <div className="mt-4 grid grid-cols-1 gap-3">
                  <div>
                    <label className="block text-xs text-zinc-400">
                      Ссылка на отчёт (только для “Отправить отчёт”)
                    </label>
                    <input
                      value={reportLink}
                      onChange={(e) => setReportLink(e.target.value)}
                      className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
                      placeholder="https://..."
                    />
                  </div>

                  <div>
                    <label className="block text-xs text-zinc-400">Комментарий (опционально)</label>
                    <textarea
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      className="mt-1 w-full min-h-[90px] resize-y rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
                      placeholder="Комментарий / причина…"
                    />
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    onClick={() => void runAction("report")}
                    disabled={itemLoading || !can("report")}
                    className="rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                    title={can("report") ? "" : "Действие недоступно"}
                  >
                    {ACTION_RU.report}
                  </button>

                  <button
                    onClick={() => void runAction("approve")}
                    disabled={itemLoading || !can("approve")}
                    className="rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                    title={can("approve") ? "" : "Действие недоступно"}
                  >
                    {ACTION_RU.approve}
                  </button>

                  <button
                    onClick={() => void runAction("reject")}
                    disabled={itemLoading || !can("reject")}
                    className="rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                    title={can("reject") ? "" : "Действие недоступно"}
                  >
                    {ACTION_RU.reject}
                  </button>

                  <button
                    onClick={() => {
                      if (!can("archive")) return;
                      const ok = window.confirm("Переместить в архив — точно?");
                      if (ok) void runAction("archive");
                    }}
                    disabled={itemLoading || !can("archive")}
                    className="rounded-md border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                    title={can("archive") ? "" : "Действие недоступно"}
                  >
                    {ACTION_RU.archive}
                  </button>
                </div>
              </div>

              <details className="mt-3 rounded-xl border border-zinc-800 bg-zinc-950/20 p-3">
                <summary className="cursor-pointer text-sm text-zinc-300">Детали (JSON)</summary>
                <pre className="mt-2 overflow-auto text-xs text-zinc-200">
                  {JSON.stringify(item ?? selectedFromList, null, 2)}
                </pre>
              </details>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
