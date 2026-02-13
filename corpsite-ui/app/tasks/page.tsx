// FILE: corpsite-ui/app/tasks/page.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGetTask, apiGetTasks, apiPostTaskAction } from "@/lib/api";
import type { AllowedAction, TaskAction, TaskDetails, TaskListItem } from "@/lib/types";

/**
 * UI: русифицированная страница задач.
 * - Заголовок: "Система личных кабинетов / Задачи"
 * - Нет "Dev" в тексте интерфейса (внутри остаётся только ключ localStorage).
 * - Есть фильтр по роли исполнителя (executor_role_id) + кнопка "Применить фильтры".
 * - Роли подтягиваются с backend: GET /directory/roles
 */

const DEV_USER_ID_KEY = "system.devUserId"; // ключ в localStorage (не показываем в UI)

const ACTION_RU: Record<string, string> = {
  report: "Отправить отчёт",
  approve: "Согласовать",
  reject: "Отклонить",
  archive: "В архив",
};

type RoleItem = {
  id: number;
  code?: string | null;
  name: string;
  is_active?: boolean;
};

function actionsRu(actions: AllowedAction[] | undefined | null): string {
  if (!actions || actions.length === 0) return "—";
  return actions.map((a) => ACTION_RU[String(a)] ?? String(a)).join(" / ");
}

function getStoredUserId(): number {
  if (typeof window === "undefined") return 1;
  const raw = window.localStorage.getItem(DEV_USER_ID_KEY);
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

function setStoredUserId(v: number): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(DEV_USER_ID_KEY, String(v));
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

function roleLabel(r: RoleItem): string {
  const code = String(r.code ?? "").trim();
  const name = String(r.name ?? "").trim();
  if (code && name) return `${name} (${code})`;
  return name || code || `Роль №${r.id}`;
}

function normalizeUserNotFound(msg: string): string {
  const s = String(msg || "").trim();
  if (!s) return "Ошибка запроса";
  if (/User not found/i.test(s)) return "Пользователь с таким ID не найден (нужно указывать user_id).";
  if (/\(404\)/.test(s) && /not found/i.test(s)) return "Пользователь с таким ID не найден (нужно указывать user_id).";
  return s;
}

export default function TasksPage() {
  // "Режим разработчика" (фактически: выбор user_id для тестов)
  const [userId, setUserIdState] = useState<number>(1);

  // paging
  const [limit, setLimit] = useState<number>(50);
  const [offset, setOffset] = useState<number>(0);

  // roles filter
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [rolesLoading, setRolesLoading] = useState(false);
  const [rolesError, setRolesError] = useState<string | null>(null);
  const [executorRoleId, setExecutorRoleId] = useState<number | "">("");

  // list
  const [list, setList] = useState<TaskListItem[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);

  // selection + details
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [item, setItem] = useState<TaskDetails | null>(null);
  const [itemLoading, setItemLoading] = useState(false);
  const [itemError, setItemError] = useState<string | null>(null);

  // action form
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

  async function reloadRoles(uid?: number) {
    const currentUserId = uid ?? userId;

    setRolesLoading(true);
    setRolesError(null);

    try {
      const res = await fetch("http://127.0.0.1:8000/directory/roles", {
        method: "GET",
        headers: { "X-User-Id": String(currentUserId) },
        cache: "no-store",
      });

      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw { status: res.status, message: text || "Не удалось загрузить роли" };
      }

      const json = (await res.json()) as any;
      const items = Array.isArray(json?.items) ? (json.items as any[]) : [];

      const parsed: RoleItem[] = items
        .map((x) => ({
          id: Number(x?.id ?? 0),
          code: x?.code ?? null,
          name: String(x?.name ?? "").trim(),
          is_active: Boolean(x?.is_active ?? true),
        }))
        .filter((x) => Number.isFinite(x.id) && x.id > 0);

      parsed.sort((a, b) => a.id - b.id);
      setRoles(parsed);
    } catch (e: any) {
      const st = e?.status;
      const msg = normalizeUserNotFound(e?.message || "Не удалось загрузить роли");
      setRoles([]);
      setRolesError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setRolesLoading(false);
    }
  }

  async function reloadList(uid?: number) {
    const currentUserId = uid ?? userId;

    setListLoading(true);
    setListError(null);

    try {
      const data = await apiGetTasks({
        devUserId: currentUserId,
        limit,
        offset,
        executor_role_id: executorRoleId === "" ? undefined : Number(executorRoleId),
      } as any);

      setList(data);

      if (selectedId && !data.some((x: any) => taskIdOf(x) === selectedId)) {
        setSelectedId(null);
        setItem(null);
      }
    } catch (e: any) {
      const st = e?.status;
      const msg = normalizeUserNotFound(e?.message || "Не удалось загрузить список задач");
      setList([]);
      setSelectedId(null);
      setItem(null);
      setListError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setListLoading(false);
    }
  }

  async function reloadItem(id: number, uid?: number) {
    const currentUserId = uid ?? userId;

    setItemLoading(true);
    setItemError(null);

    try {
      const data = await apiGetTask({ devUserId: currentUserId, taskId: id, includeArchived: true });
      setItem(data);
    } catch (e: any) {
      const st = e?.status;
      const msg = normalizeUserNotFound(e?.message || "Не удалось загрузить задачу");
      setItem(null);
      setItemError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setItemLoading(false);
    }
  }

  async function runAction(action: TaskAction) {
    if (!selectedId) return;

    const currentUserId = userId;

    setItemError(null);
    setItemLoading(true);

    try {
      if (action === "report") {
        const link = reportLink.trim();
        if (!link) {
          setItemError("Отчёт: укажи ссылку (report_link).");
          return;
        }

        await apiPostTaskAction({
          devUserId: currentUserId,
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
          devUserId: currentUserId,
          taskId: selectedId,
          action,
          payload: reason.trim() ? ({ reason: reason.trim() } as any) : undefined,
        });
      }

      await Promise.all([reloadItem(selectedId, currentUserId), reloadList(currentUserId)]);
    } catch (e: any) {
      const st = e?.status;
      const msg = normalizeUserNotFound(e?.message || "Не удалось выполнить действие");
      setItemError(st ? `(${st}) ${msg}` : msg);
    } finally {
      setItemLoading(false);
    }
  }

  useEffect(() => {
    const uid = getStoredUserId();
    setUserIdState(uid);

    void reloadRoles(uid);
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
          <div className="text-xl font-semibold">Система личных кабинетов / Задачи</div>

          <div className="flex items-center gap-2">
            <div className="text-xs text-zinc-400">
              <div>Режим разработчика</div>
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
                setStoredUserId(userId);
                setOffset(0);
                void reloadRoles(userId);
                void reloadList(userId);
                if (selectedId) void reloadItem(selectedId, userId);
                setItemError(null);
              }}
              className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800"
            >
              Применить
            </button>
          </div>
        </div>

        <div className="mt-2 text-xs text-zinc-400">
          Режим разработчика: вводится <span className="text-zinc-200">user_id</span> (не role_id). Фильтр “Роль исполнителя” — это{" "}
          <span className="text-zinc-200">executor_role_id</span>.
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
                Обновить
              </button>
            </div>

            {/* Filters */}
            <div className="mb-3 rounded-lg border border-zinc-800 bg-zinc-950/30 p-3">
              <div className="mb-2 text-xs uppercase tracking-wide text-zinc-300">Фильтры</div>

              <div className="grid grid-cols-1 gap-2">
                <div>
                  <label className="block text-xs text-zinc-400">Роль исполнителя</label>
                  <select
                    value={executorRoleId === "" ? "" : String(executorRoleId)}
                    onChange={(e) => {
                      const v = e.target.value;
                      setExecutorRoleId(v === "" ? "" : Number(v));
                    }}
                    className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                    disabled={rolesLoading}
                  >
                    <option value="">Все роли</option>
                    {roles.map((r) => (
                      <option key={r.id} value={String(r.id)}>
                        {roleLabel(r)}
                      </option>
                    ))}
                  </select>

                  {rolesError ? <div className="mt-1 text-xs text-red-400">roles: {rolesError}</div> : null}
                  {rolesLoading ? <div className="mt-1 text-xs text-zinc-500">roles: загрузка…</div> : null}
                </div>

                <div className="grid grid-cols-2 gap-2">
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
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      setOffset(0);
                      void reloadList(userId);
                    }}
                    className="flex-1 rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                    disabled={listLoading}
                  >
                    Применить фильтры
                  </button>

                  <button
                    onClick={() => {
                      setExecutorRoleId("");
                      setOffset(0);
                      void reloadList(userId);
                    }}
                    className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                    disabled={listLoading}
                    title="Сбросить фильтр роли"
                  >
                    Сбросить
                  </button>
                </div>
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
                      <span>№{id}</span>
                      <span>доступно: {actionsRu(actions)}</span>
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
                Обновить
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
                      <div className="mt-1 text-sm text-zinc-400">№{selectedId}</div>
                    </div>
                    <div className="rounded-md border border-zinc-700 px-2 py-1 text-xs text-zinc-200">{effectiveStatus}</div>
                  </div>

                  <div className="mt-2 text-xs text-zinc-500">
                    доступно: <span className="text-zinc-200">{actionsRu(effectiveAllowed)}</span>
                  </div>

                  <div className="mt-3 grid grid-cols-1 gap-2">
                    <div>
                      <label className="block text-xs text-zinc-400">Ссылка на отчёт (только для “Отправить отчёт”)</label>
                      <input
                        value={reportLink}
                        onChange={(e) => setReportLink(e.target.value)}
                        className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                        placeholder="https://..."
                      />
                    </div>

                    <div>
                      <label className="block text-xs text-zinc-400">Комментарий (опционально)</label>
                      <textarea
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        className="mt-1 w-full min-h-[80px] resize-y rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                        placeholder="Комментарий / причина..."
                      />
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      onClick={() => void runAction("report")}
                      disabled={itemLoading || !can("report")}
                      className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      title={can("report") ? "" : "Действие недоступно"}
                    >
                      {ACTION_RU.report}
                    </button>

                    <button
                      onClick={() => void runAction("approve")}
                      disabled={itemLoading || !can("approve")}
                      className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      title={can("approve") ? "" : "Действие недоступно"}
                    >
                      {ACTION_RU.approve}
                    </button>

                    <button
                      onClick={() => void runAction("reject")}
                      disabled={itemLoading || !can("reject")}
                      className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
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
                      className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      title={can("archive") ? "" : "Действие недоступно"}
                    >
                      {ACTION_RU.archive}
                    </button>
                  </div>
                </div>

                <details className="mt-3 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
                  <summary className="cursor-pointer text-sm text-zinc-300">Исходные данные (JSON)</summary>
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
