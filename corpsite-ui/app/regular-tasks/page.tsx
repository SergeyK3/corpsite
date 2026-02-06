// FILE: corpsite-ui/app/regular-tasks/page.tsx
"use client";

import { useEffect, useMemo, useState } from "react";

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

function env(name: string, fallback = ""): string {
  const v = process.env[name];
  return (v ?? fallback).toString().trim();
}

const API_BASE_URL = env("NEXT_PUBLIC_API_BASE_URL", "http://127.0.0.1:8000");

async function readJsonSafe(res: Response): Promise<any> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

type APIError = {
  status: number;
  code?: string;
  message?: string;
  details?: any;
};

function toApiError(status: number, body: any, meta?: Record<string, any>): APIError {
  const err: APIError = {
    status,
    code: body?.code,
    message: body?.message ?? body?.detail ?? body?.error ?? "Request failed",
    details: body,
  };
  if (meta) (err as any).meta = meta;
  return err;
}

function buildUrl(path: string, query?: Record<string, string | number | boolean | undefined>): URL {
  const url = new URL(path, API_BASE_URL);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined) continue;
      url.searchParams.set(k, String(v));
    }
  }
  return url;
}

function buildHeaders(devUserId: number, extra?: Record<string, string>): HeadersInit {
  return {
    "X-User-Id": String(devUserId),
    ...(extra ?? {}),
  };
}

export type RegularTask = {
  regular_task_id: number;

  title: string;
  description?: string | null;
  code?: string | null;

  is_active?: boolean;

  executor_role_id?: number | null;

  schedule_type?: string | null;
  schedule_params?: any;

  create_offset_days?: number;
  due_offset_days?: number;

  created_by_user_id?: number | null;
  updated_at?: string | null;
};

async function apiListRegularTasks(params: {
  devUserId: number;
  status?: "active" | "inactive" | "all";
  q?: string;
  schedule_type?: string;
  executor_role_id?: number;
  limit?: number;
  offset?: number;
}): Promise<{ items: RegularTask[]; total?: number }> {
  const url = buildUrl("/regular-tasks", {
    status: params.status ?? "active",
    q: params.q?.trim() ? params.q.trim() : undefined,
    schedule_type: params.schedule_type?.trim() ? params.schedule_type.trim() : undefined,
    executor_role_id: params.executor_role_id ? params.executor_role_id : undefined,
    limit: params.limit ?? 50,
    offset: params.offset ?? 0,
  });

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: buildHeaders(params.devUserId),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, { method: "GET", url: url.toString() });
  }

  if (Array.isArray(body)) return { items: body as RegularTask[] };
  if (body?.items && Array.isArray(body.items)) return { items: body.items as RegularTask[], total: body.total };
  return { items: [] };
}

async function apiGetRegularTask(params: { devUserId: number; id: number }): Promise<RegularTask> {
  const url = buildUrl(`/regular-tasks/${params.id}`);

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: buildHeaders(params.devUserId),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, { method: "GET", url: url.toString() });
  }

  return body as RegularTask;
}

async function apiCreateRegularTask(params: { devUserId: number; payload: Record<string, any> }): Promise<any> {
  const url = buildUrl("/regular-tasks");

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: buildHeaders(params.devUserId, { "Content-Type": "application/json" }),
    body: JSON.stringify(params.payload ?? {}),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, { method: "POST", url: url.toString() });
  }
  return body;
}

async function apiPatchRegularTask(params: {
  devUserId: number;
  id: number;
  payload: Record<string, any>;
}): Promise<any> {
  const url = buildUrl(`/regular-tasks/${params.id}`);

  const res = await fetch(url.toString(), {
    method: "PATCH",
    headers: buildHeaders(params.devUserId, { "Content-Type": "application/json" }),
    body: JSON.stringify(params.payload ?? {}),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, { method: "PATCH", url: url.toString() });
  }
  return body;
}

async function apiActivateRegularTask(params: { devUserId: number; id: number; active: boolean }): Promise<any> {
  const url = buildUrl(`/regular-tasks/${params.id}/${params.active ? "activate" : "deactivate"}`);

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: buildHeaders(params.devUserId),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, { method: "POST", url: url.toString() });
  }
  return body;
}

function safeInt(v: any, fallback: number): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function asTrimmedOrNull(v: any): string | null {
  if (typeof v !== "string") return null;
  const s = v.trim();
  return s ? s : null;
}

function jsonPretty(v: any): string {
  try {
    if (v === undefined) return "";
    if (v === null) return "";
    if (typeof v === "string") return v;
    return JSON.stringify(v, null, 2);
  } catch {
    return "";
  }
}

function parseJsonOrEmpty(text: string): any {
  const s = (text ?? "").trim();
  if (!s) return {};
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

export default function RegularTasksPage() {
  const [userId, setUserIdState] = useState<number>(1);

  const [status, setStatus] = useState<"active" | "inactive" | "all">("active");
  const [q, setQ] = useState<string>("");

  const [items, setItems] = useState<RegularTask[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [card, setCard] = useState<RegularTask | null>(null);
  const [cardLoading, setCardLoading] = useState(false);
  const [cardError, setCardError] = useState<string | null>(null);

  // UX modes:
  // - view: show card + actions
  // - create: show card header + embedded create form
  // - edit: show card header + embedded edit form (actions activate/deactivate hidden)
  const [mode, setMode] = useState<"view" | "create" | "edit">("view");

  // form (create/edit)
  const [fTitle, setFTitle] = useState<string>("");
  const [fDescription, setFDescription] = useState<string>("");
  const [fCode, setFCode] = useState<string>("");
  const [fExecutorRoleId, setFExecutorRoleId] = useState<string>("");
  const [fScheduleType, setFScheduleType] = useState<string>("");
  const [fScheduleParams, setFScheduleParams] = useState<string>("{}");
  const [fCreateOffsetDays, setFCreateOffsetDays] = useState<string>("0");
  const [fDueOffsetDays, setFDueOffsetDays] = useState<string>("0");

  const selectedFromList = useMemo(() => {
    if (!selectedId) return null;
    return items.find((x) => x.regular_task_id === selectedId) ?? null;
  }, [items, selectedId]);

  function resetFormFromTask(t?: RegularTask | null) {
    const x = t ?? null;
    setFTitle(String(x?.title ?? ""));
    setFDescription(String(x?.description ?? ""));
    setFCode(String(x?.code ?? ""));
    setFExecutorRoleId(x?.executor_role_id != null ? String(x.executor_role_id) : "");
    setFScheduleType(String(x?.schedule_type ?? ""));
    setFScheduleParams(jsonPretty(x?.schedule_params ?? {}));
    setFCreateOffsetDays(String(x?.create_offset_days ?? 0));
    setFDueOffsetDays(String(x?.due_offset_days ?? 0));
  }

  async function reloadList(uid?: number) {
    const devUserId = uid ?? userId;
    setListLoading(true);
    setListError(null);
    try {
      const data = await apiListRegularTasks({
        devUserId,
        status,
        q: q.trim() ? q.trim() : undefined,
        limit: 50,
        offset: 0,
      });
      setItems(data.items);

      if (selectedId && !data.items.some((x) => x.regular_task_id === selectedId)) {
        setSelectedId(null);
        setCard(null);
        setMode("view");
      }
    } catch (e: any) {
      const statusCode = e?.status;
      const msg = e?.message || "Failed to fetch regular tasks";
      setItems([]);
      setSelectedId(null);
      setCard(null);
      setMode("view");
      setListError(statusCode ? `(${statusCode}) ${msg}` : msg);
    } finally {
      setListLoading(false);
    }
  }

  async function reloadCard(id: number, uid?: number) {
    const devUserId = uid ?? userId;
    setCardLoading(true);
    setCardError(null);
    try {
      const data = await apiGetRegularTask({ devUserId, id });
      setCard(data);
      if (mode === "edit") resetFormFromTask(data);
    } catch (e: any) {
      const statusCode = e?.status;
      const msg = e?.message || "Failed to fetch regular task";
      setCard(null);
      setCardError(statusCode ? `(${statusCode}) ${msg}` : msg);
    } finally {
      setCardLoading(false);
    }
  }

  function validatePayload(p: Record<string, any>): string | null {
    const title = String(p.title ?? "").trim();
    if (!title) return "title is required";
    if (p.schedule_params === null) return "schedule_params must be valid JSON";
    return null;
  }

  function buildPayload(): Record<string, any> {
    const scheduleParamsParsed = parseJsonOrEmpty(fScheduleParams);

    const payload: Record<string, any> = {
      title: fTitle.trim(),
      description: asTrimmedOrNull(fDescription),
      code: asTrimmedOrNull(fCode),
      executor_role_id: fExecutorRoleId.trim() ? safeInt(fExecutorRoleId, 0) : null,
      schedule_type: asTrimmedOrNull(fScheduleType),
      schedule_params: scheduleParamsParsed,
      create_offset_days: safeInt(fCreateOffsetDays, 0),
      due_offset_days: safeInt(fDueOffsetDays, 0),
    };

    if (payload.description === null) delete payload.description;
    if (payload.code === null) delete payload.code;
    if (payload.executor_role_id === null) delete payload.executor_role_id;
    if (payload.schedule_type === null) delete payload.schedule_type;

    return payload;
  }

  async function onCreate() {
    setCardError(null);
    setCardLoading(true);

    try {
      const payload = buildPayload();
      const err = validatePayload(payload);
      if (err) throw new Error(err);

      const res = await apiCreateRegularTask({ devUserId: userId, payload });
      const newId = Number(res?.regular_task_id ?? res?.id ?? 0);

      await reloadList(userId);

      if (newId > 0) {
        setSelectedId(newId);
        setMode("view");
        await reloadCard(newId, userId);
      } else {
        setMode("view");
      }
    } catch (e: any) {
      const statusCode = e?.status;
      const msg = e?.message || String(e) || "Create failed";
      setCardError(statusCode ? `(${statusCode}) ${msg}` : msg);
    } finally {
      setCardLoading(false);
    }
  }

  async function onSaveEdit() {
    if (!selectedId) return;

    setCardError(null);
    setCardLoading(true);

    try {
      const payload = buildPayload();
      const err = validatePayload(payload);
      if (err) throw new Error(err);

      await apiPatchRegularTask({ devUserId: userId, id: selectedId, payload });
      setMode("view");
      await Promise.all([reloadCard(selectedId, userId), reloadList(userId)]);
    } catch (e: any) {
      const statusCode = e?.status;
      const msg = e?.message || String(e) || "Update failed";
      setCardError(statusCode ? `(${statusCode}) ${msg}` : msg);
    } finally {
      setCardLoading(false);
    }
  }

  async function onToggleActive(active: boolean) {
    if (!selectedId) return;

    setCardError(null);
    setCardLoading(true);

    try {
      await apiActivateRegularTask({ devUserId: userId, id: selectedId, active });
      await Promise.all([reloadCard(selectedId, userId), reloadList(userId)]);
    } catch (e: any) {
      const statusCode = e?.status;
      const msg = e?.message || "Action failed";
      setCardError(statusCode ? `(${statusCode}) ${msg}` : msg);
    } finally {
      setCardLoading(false);
    }
  }

  // Inline form state
  const draftPayload = useMemo(() => buildPayload(), [
    fTitle,
    fDescription,
    fCode,
    fExecutorRoleId,
    fScheduleType,
    fScheduleParams,
    fCreateOffsetDays,
    fDueOffsetDays,
  ]);

  const draftError = useMemo(() => validatePayload(draftPayload), [draftPayload]);

  useEffect(() => {
    const uid = getDevUserId();
    setUserIdState(uid);
    void reloadList(uid);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setCard(null);
      setCardError(null);
      if (mode !== "create") setMode("view");
      return;
    }
    void reloadCard(selectedId, userId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, userId]);

  const activeFlag =
    (card?.is_active ?? selectedFromList?.is_active) === true
      ? true
      : (card?.is_active ?? selectedFromList?.is_active) === false
        ? false
        : undefined;

  const cardTitle =
    mode === "create"
      ? "Создание"
      : mode === "edit"
        ? `Редактирование • #${selectedId ?? "—"}`
        : card?.title ?? selectedFromList?.title ?? (selectedId ? `#${selectedId}` : "Карточка");

  function openCreate() {
    setSelectedId(null);
    setCard(null);
    setMode("create");
    resetFormFromTask(null);
    setCardError(null);
  }

  function openEdit() {
    if (!selectedId) return;
    setMode("edit");
    resetFormFromTask(card ?? selectedFromList);
    setCardError(null);
  }

  function cancelInline() {
    if (mode === "create") {
      setMode("view");
      setCardError(null);
      resetFormFromTask(null);
      return;
    }
    // edit
    setMode("view");
    setCardError(null);
    if (selectedId) resetFormFromTask(card ?? selectedFromList);
  }

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
                if (selectedId) void reloadCard(selectedId, userId);
                setCardError(null);
              }}
              className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800"
            >
              Apply
            </button>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* LIST */}
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

            <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as any)}
                className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
              >
                <option value="active">active</option>
                <option value="inactive">inactive</option>
                <option value="all">all</option>
              </select>

              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none sm:col-span-2"
                placeholder="Поиск (q)"
              />
            </div>

            <div className="mb-3 flex gap-2">
              <button
                onClick={openCreate}
                className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs hover:bg-zinc-800"
              >
                + Create
              </button>

              <button
                onClick={() => void reloadList(userId)}
                className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs hover:bg-zinc-800"
              >
                Apply filters
              </button>
            </div>

            {listError ? <div className="mb-3 text-sm text-red-400">Ошибка списка: {listError}</div> : null}
            {listLoading ? <div className="text-sm text-zinc-400">Загрузка…</div> : null}

            <div className="space-y-2">
              {items.map((t) => {
                const id = t.regular_task_id;
                const active = selectedId === id;
                const isActive = t.is_active === true ? "active" : t.is_active === false ? "inactive" : "—";
                return (
                  <button
                    key={id}
                    onClick={() => {
                      setSelectedId(id);
                      setMode("view");
                      setCardError(null);
                    }}
                    className={[
                      "w-full rounded-lg border px-3 py-2 text-left",
                      active ? "border-zinc-600 bg-zinc-900" : "border-zinc-800 bg-zinc-950/40 hover:bg-zinc-900/60",
                    ].join(" ")}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="font-medium">{t.title || `RegularTask #${id}`}</div>
                      <div className="text-xs text-zinc-400">{isActive}</div>
                    </div>
                    <div className="mt-1 text-xs text-zinc-500">
                      #{id}
                      {t.code ? ` • code: ${t.code}` : ""}
                      {t.executor_role_id != null ? ` • role: ${t.executor_role_id}` : ""}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* CARD */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm uppercase tracking-wide text-zinc-300">Карточка</div>
              <button
                onClick={() => (selectedId ? void reloadCard(selectedId, userId) : null)}
                className="rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs hover:bg-zinc-800"
                disabled={!selectedId || cardLoading}
              >
                Refresh
              </button>
            </div>

            {cardError ? <div className="mb-3 text-sm text-red-400">Ошибка: {cardError}</div> : null}
            {cardLoading ? <div className="mb-3 text-sm text-zinc-400">Загрузка…</div> : null}

            {/* Header */}
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
              <div className="text-lg font-semibold">{cardTitle}</div>

              {mode === "view" && selectedId ? (
                <>
                  <div className="mt-1 text-sm text-zinc-400">
                    Статус:{" "}
                    <span className="text-zinc-200">
                      {activeFlag === true ? "active" : activeFlag === false ? "inactive" : "—"}
                    </span>{" "}
                    • #{selectedId}
                  </div>
                  <div className="mt-2 text-xs text-zinc-400">
                    code: <span className="text-zinc-200">{card?.code ?? selectedFromList?.code ?? "—"}</span> •
                    schedule_type:{" "}
                    <span className="text-zinc-200">{card?.schedule_type ?? selectedFromList?.schedule_type ?? "—"}</span>{" "}
                    • role:{" "}
                    <span className="text-zinc-200">{card?.executor_role_id ?? selectedFromList?.executor_role_id ?? "—"}</span>
                  </div>
                </>
              ) : mode === "create" ? (
                <div className="mt-1 text-sm text-zinc-400">
                  Поля соответствуют public.regular_tasks (title, description, code, executor_role_id, schedule_type, schedule_params, create_offset_days, due_offset_days).
                </div>
              ) : mode === "edit" ? (
                <div className="mt-1 text-sm text-zinc-400">
                  Редактирование полей public.regular_tasks для шаблона #{selectedId}.
                </div>
              ) : (
                <div className="mt-1 text-sm text-zinc-400">Выберите шаблон слева или нажмите Create.</div>
              )}
            </div>

            {/* Actions (view only) */}
            {mode === "view" ? (
              <div className="mt-3 rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
                <div className="mb-2 text-sm font-semibold">Действия</div>

                {!selectedId ? (
                  <div className="text-sm text-zinc-400">Нет выбранного шаблона.</div>
                ) : (
                  <>
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={openEdit}
                        disabled={!selectedId || cardLoading}
                        className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      >
                        Edit
                      </button>

                      <button
                        onClick={() => void onToggleActive(true)}
                        disabled={!selectedId || cardLoading}
                        className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      >
                        Activate
                      </button>

                      <button
                        onClick={() => void onToggleActive(false)}
                        disabled={!selectedId || cardLoading}
                        className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      >
                        Deactivate
                      </button>
                    </div>

                    <div className="mt-2 text-xs text-zinc-500">
                      Примечание: список/карточка используют /regular-tasks и /regular-tasks/{`{id}`} из OpenAPI.
                    </div>
                  </>
                )}
              </div>
            ) : null}

            {/* Inline form (create/edit) */}
            {mode === "create" || mode === "edit" ? (
              <div className="mt-3 space-y-3">
                <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
                  <div className="grid grid-cols-1 gap-3">
                    <div>
                      <label className="block text-xs text-zinc-400">title *</label>
                      <input
                        value={fTitle}
                        onChange={(e) => setFTitle(e.target.value)}
                        className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                        placeholder="Например: Еженедельный отчёт отдела"
                      />
                    </div>

                    <div>
                      <label className="block text-xs text-zinc-400">description</label>
                      <textarea
                        value={fDescription}
                        onChange={(e) => setFDescription(e.target.value)}
                        className="mt-1 w-full min-h-[84px] resize-y rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                        placeholder="Описание (опционально)"
                      />
                    </div>

                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <div>
                        <label className="block text-xs text-zinc-400">code</label>
                        <input
                          value={fCode}
                          onChange={(e) => setFCode(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                          placeholder="Уникальный код (опционально)"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-400">executor_role_id</label>
                        <input
                          value={fExecutorRoleId}
                          onChange={(e) => setFExecutorRoleId(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                          inputMode="numeric"
                          placeholder="Напр: 1"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <div>
                        <label className="block text-xs text-zinc-400">schedule_type</label>
                        <input
                          value={fScheduleType}
                          onChange={(e) => setFScheduleType(e.target.value)}
                          className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                          placeholder='Напр: "weekly" / "monthly"'
                        />
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-xs text-zinc-400">create_offset_days</label>
                          <input
                            value={fCreateOffsetDays}
                            onChange={(e) => setFCreateOffsetDays(e.target.value)}
                            className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                            inputMode="numeric"
                            placeholder="0"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-zinc-400">due_offset_days</label>
                          <input
                            value={fDueOffsetDays}
                            onChange={(e) => setFDueOffsetDays(e.target.value)}
                            className="mt-1 w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm outline-none"
                            inputMode="numeric"
                            placeholder="0"
                          />
                        </div>
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs text-zinc-400">schedule_params (JSON)</label>
                      <textarea
                        value={fScheduleParams}
                        onChange={(e) => setFScheduleParams(e.target.value)}
                        className="mt-1 w-full min-h-[140px] resize-y rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 font-mono text-xs outline-none"
                        placeholder='Напр: {"weekday":1} или {"bymonthday":[27]}'
                      />
                      {draftError ? (
                        <div className="mt-2 text-xs text-red-400">Ошибка: {draftError}</div>
                      ) : (
                        <div className="mt-2 text-xs text-zinc-500">JSON валиден. Можно сохранять.</div>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => void (mode === "create" ? onCreate() : onSaveEdit())}
                        disabled={cardLoading || !!draftError}
                        className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      >
                        {mode === "create" ? "Create" : "Save"}
                      </button>

                      <button
                        onClick={cancelInline}
                        disabled={cardLoading}
                        className="rounded-md border border-zinc-800 bg-zinc-900 px-4 py-2 text-sm hover:bg-zinc-800 disabled:opacity-60"
                      >
                        Cancel
                      </button>
                    </div>

                    <details className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
                      <summary className="cursor-pointer text-sm text-zinc-300">Draft payload</summary>
                      <pre className="mt-2 overflow-auto text-xs text-zinc-200">
                        {JSON.stringify(draftPayload, null, 2)}
                      </pre>
                    </details>
                  </div>
                </div>
              </div>
            ) : null}

            {/* Raw JSON (view only) */}
            {mode === "view" ? (
              <details className="mt-3 rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
                <summary className="cursor-pointer text-sm text-zinc-300">Raw JSON</summary>
                <pre className="mt-2 overflow-auto text-xs text-zinc-200">{JSON.stringify(card ?? selectedFromList, null, 2)}</pre>
              </details>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
