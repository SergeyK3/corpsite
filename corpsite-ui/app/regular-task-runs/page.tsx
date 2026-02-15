// FILE: corpsite-ui/app/regular-task-runs/page.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { apiAuthMe, clearAccessToken, isAuthed } from "@/lib/api";

type MeInfo = {
  user_id?: number;
  role_id?: number;
  role_name_ru?: string;
  role_name?: string;
  full_name?: string;
  login?: string;
};

type APIErrorLike = {
  status?: number;
  message?: string;
  details?: any;
  body?: any;
};

function formatUserError(e: any): string {
  const status = Number((e as APIErrorLike)?.status ?? 0);
  const body =
    (e as APIErrorLike)?.details ??
    (e as APIErrorLike)?.body ??
    undefined;
  const msg = String(
    (e as APIErrorLike)?.message ??
      body?.message ??
      body?.detail ??
      body?.error ??
      "",
  ).trim();

  const base =
    status === 401
      ? "Требуется авторизация."
      : status === 403
        ? "Недостаточно прав."
        : status === 404
          ? "Объект не найден."
          : status === 409
            ? "Конфликт данных. Обновите страницу и попробуйте снова."
            : status === 422
              ? "Некорректные данные."
              : status >= 500
                ? "Ошибка сервера. Попробуйте позже."
                : "Не удалось выполнить запрос.";

  return status
    ? `(${status}) ${base}${msg ? ` ${msg}` : ""}`
    : `${base}${msg ? ` ${msg}` : ""}`;
}

function isUnauthorized(e: any): boolean {
  return Number((e as APIErrorLike)?.status ?? 0) === 401;
}

function parseIntSetCsv(raw: string): Set<number> {
  const out = new Set<number>();
  const s = String(raw ?? "").trim();
  if (!s) return out;
  for (const part of s.split(",")) {
    const n = Number(String(part).trim());
    if (Number.isFinite(n) && n > 0) out.add(n);
  }
  return out;
}

function env(name: string, fallback = ""): string {
  const v = process.env[name];
  return (v ?? fallback).toString().trim();
}

type RegularTaskRun = {
  run_id: number;
  started_at: string;
  finished_at?: string | null;
  status: string;
  stats?: any;
  errors?: any;
};

type RegularTaskRunItem = {
  item_id: number;
  run_id: number;
  regular_task_id: number;
  status: string;
  started_at: string;
  finished_at?: string | null;
  period_id?: number | null;
  executor_role_id?: number | null;
  is_due: boolean;
  created_tasks: number;
  error?: string | null;
};

async function readJsonSafe(res: Response): Promise<any> {
  const text = await res.text().catch(() => "");
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

function normalizeList<T>(body: any): T[] {
  if (Array.isArray(body)) return body as T[];
  if (body?.items && Array.isArray(body.items)) return body.items as T[];
  return [];
}

function getApiBase(): string {
  const base = env("NEXT_PUBLIC_API_BASE_URL", "http://127.0.0.1:8000").replace(/\/+$/, "");
  return base || "http://127.0.0.1:8000";
}

function getBearer(): string {
  if (typeof window === "undefined") return "";
  try {
    return (window.sessionStorage.getItem("access_token") ?? "").toString().trim();
  } catch {
    return "";
  }
}

async function apiGetRuns(): Promise<RegularTaskRun[]> {
  const base = getApiBase();
  const url = new URL("/regular-task-runs", base);

  const tok = getBearer();
  const res = await fetch(url.toString(), {
    method: "GET",
    headers: tok ? { Authorization: `Bearer ${tok}`, Accept: "application/json" } : { Accept: "application/json" },
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    const e: any = { status: res.status, message: body?.message ?? body?.detail ?? "Request failed", details: body };
    throw e;
  }

  return normalizeList<RegularTaskRun>(body);
}

async function apiGetRunItems(runId: number): Promise<RegularTaskRunItem[]> {
  const base = getApiBase();
  const url = new URL(`/regular-task-runs/${runId}/items`, base);

  const tok = getBearer();
  const res = await fetch(url.toString(), {
    method: "GET",
    headers: tok ? { Authorization: `Bearer ${tok}`, Accept: "application/json" } : { Accept: "application/json" },
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    const e: any = { status: res.status, message: body?.message ?? body?.detail ?? "Request failed", details: body };
    throw e;
  }

  return normalizeList<RegularTaskRunItem>(body);
}

function issueLabel(s: string): string {
  const x = String(s ?? "").trim();
  if (!x) return "—";
  if (x.includes("unsupported schedule_type: yearly")) return "yearly не поддержан";
  if (x.includes("schedule_params.bymonthday must be a non-empty list")) return "monthly без bymonthday";
  return x;
}

export default function RegularTaskRunsPage() {
  const router = useRouter();

  // auth/me
  const [me, setMe] = useState<MeInfo | null>(null);
  const [meLoading, setMeLoading] = useState(true);
  const [meError, setMeError] = useState<string | null>(null);

  const roleTitle = useMemo(() => {
    const t = String(me?.role_name_ru ?? me?.role_name ?? "").trim();
    return t || "Сотрудник";
  }, [me]);

  // access: runs for support/admin only
  const SUPPORT_ROLE_IDS = useMemo(() => {
    const fromEnv = parseIntSetCsv(env("NEXT_PUBLIC_SUPPORT_ROLE_IDS", ""));
    if (fromEnv.size > 0) return fromEnv;
    return new Set<number>([1]); // ADMIN
  }, []);

  const canSeeRuns = useMemo(() => {
    const rid = Number(me?.role_id ?? 0);
    return rid > 0 && SUPPORT_ROLE_IDS.has(rid);
  }, [me, SUPPORT_ROLE_IDS]);

  // runs
  const [runs, setRuns] = useState<RegularTaskRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState<string | null>(null);

  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);

  // items
  const [items, setItems] = useState<RegularTaskRunItem[]>([]);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [itemsError, setItemsError] = useState<string | null>(null);

  // ui filters
  const [onlyIssues, setOnlyIssues] = useState(false);
  const [search, setSearch] = useState("");

  function redirectToLogin() {
    clearAccessToken();
    router.replace("/login");
  }

  async function loadRuns() {
    setRunsLoading(true);
    setRunsError(null);
    try {
      const data = await apiGetRuns();
      setRuns(data);

      if (selectedRunId && !data.some((r) => r.run_id === selectedRunId)) {
        setSelectedRunId(null);
        setItems([]);
      }
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      setRuns([]);
      setSelectedRunId(null);
      setItems([]);
      setRunsError(formatUserError(e));
    } finally {
      setRunsLoading(false);
    }
  }

  async function openRun(runId: number) {
    setSelectedRunId(runId);
    setItems([]);
    setItemsLoading(true);
    setItemsError(null);

    try {
      const data = await apiGetRunItems(runId);
      setItems(data);
    } catch (e: any) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      setItems([]);
      setItemsError(formatUserError(e));
    } finally {
      setItemsLoading(false);
    }
  }

  // bootstrap auth
  useEffect(() => {
    void (async () => {
      setMeLoading(true);
      setMeError(null);

      if (!isAuthed()) {
        router.replace("/login");
        return;
      }

      try {
        const data = (await apiAuthMe()) as any;
        setMe(data as MeInfo);
      } catch (e: any) {
        if (isUnauthorized(e)) {
          redirectToLogin();
          return;
        }
        setMeError(formatUserError(e));
        setMe(null);
      } finally {
        setMeLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // initial runs load
  useEffect(() => {
    if (meLoading) return;
    if (!me || !canSeeRuns) return;
    void loadRuns();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meLoading, me, canSeeRuns]);

  const selectedRun = useMemo(() => {
    if (!selectedRunId) return null;
    return runs.find((r) => r.run_id === selectedRunId) ?? null;
  }, [runs, selectedRunId]);

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((it) => {
      if (onlyIssues && !String(it.error ?? "").trim()) return false;
      if (!q) return true;
      const hay = [
        it.item_id,
        it.regular_task_id,
        it.status,
        it.executor_role_id ?? "",
        it.period_id ?? "",
        it.error ?? "",
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [items, onlyIssues, search]);

  function logout() {
    clearAccessToken();
    router.replace("/login");
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      {/* TITLE */}
      <div className="mb-6">
        <div className="text-2xl font-semibold text-zinc-100">{roleTitle}</div>
        <div className="mt-1 text-sm text-zinc-400">Запуски регулярных задач</div>
      </div>

      {/* TOP BAR */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="text-sm text-zinc-400">{meLoading ? "Загрузка профиля…" : meError ? "Ошибка профиля" : null}</div>

        <div className="flex items-center gap-2">
          <Link
            href="/"
            className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60"
            title="Перейти в кабинет"
          >
            Кабинет
          </Link>

          <Link
            href="/regular-tasks"
            className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60"
            title="Перейти к шаблонам"
          >
            Шаблоны
          </Link>

          <button
            onClick={logout}
            className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60"
            title="Сбросить токен и перейти на страницу входа"
          >
            Выйти
          </button>
        </div>
      </div>

      {meError ? (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{meError}</div>
      ) : null}

      {!meLoading && me && !canSeeRuns ? (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-200">
          Доступ к разделу запусков ограничен. Этот раздел предназначен для службы поддержки/администраторов.
        </div>
      ) : null}

      {!meLoading && me && canSeeRuns ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {/* RUNS LIST */}
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-zinc-100">Запуски</div>
              <button
                onClick={() => void loadRuns()}
                className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                disabled={runsLoading}
              >
                {runsLoading ? "Обновление…" : "Обновить"}
              </button>
            </div>

            {runsError ? <div className="mb-3 text-sm text-red-300">Ошибка: {runsError}</div> : null}
            {runsLoading ? <div className="text-sm text-zinc-400">Загрузка…</div> : null}

            {!runsLoading && !runsError && runs.length === 0 ? (
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3 text-sm text-zinc-400">Запусков нет.</div>
            ) : null}

            <div className="space-y-2">
              {runs.map((r) => {
                const active = selectedRunId === r.run_id;
                const hasErrors = !!(r.errors && Object.keys(r.errors ?? {}).length > 0);
                return (
                  <button
                    key={r.run_id}
                    onClick={() => void openRun(r.run_id)}
                    className={[
                      "w-full rounded-lg border px-3 py-2 text-left",
                      active ? "border-zinc-600 bg-zinc-900" : "border-zinc-800 bg-zinc-950/40 hover:bg-zinc-900/60",
                    ].join(" ")}
                    title="Открыть items"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="font-medium text-zinc-100">Run #{r.run_id}</div>
                      <div className="text-xs text-zinc-400">{r.status}</div>
                    </div>
                    <div className="mt-1 text-xs text-zinc-500">
                      {r.started_at}
                      {hasErrors ? " • есть ошибки" : ""}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* RUN ITEMS */}
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm font-semibold text-zinc-100">
                Items {selectedRun ? `• run #${selectedRun.run_id}` : ""}
              </div>

              <button
                onClick={() => (selectedRunId ? void openRun(selectedRunId) : null)}
                className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-900/60 disabled:opacity-60"
                disabled={!selectedRunId || itemsLoading}
                title={!selectedRunId ? "Сначала выберите запуск" : "Перезагрузить items"}
              >
                {itemsLoading ? "Обновление…" : "Обновить"}
              </button>
            </div>

            {!selectedRunId ? (
              <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3 text-sm text-zinc-400">
                Выберите запуск слева.
              </div>
            ) : (
              <>
                <div className="mb-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
                  <label className="flex items-center gap-2 text-sm text-zinc-200">
                    <input
                      type="checkbox"
                      checked={onlyIssues}
                      onChange={(e) => setOnlyIssues(e.target.checked)}
                      className="h-4 w-4"
                    />
                    Только ошибки
                  </label>

                  <div className="sm:col-span-2">
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      className="w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
                      placeholder="Фильтр по id/статусу/ошибке…"
                    />
                    <div className="mt-1 text-[11px] text-zinc-500">
                      Показано: {filteredItems.length} из {items.length}
                    </div>
                  </div>
                </div>

                {itemsError ? <div className="mb-3 text-sm text-red-300">Ошибка: {itemsError}</div> : null}
                {itemsLoading ? <div className="mb-3 text-sm text-zinc-400">Загрузка…</div> : null}

                {!itemsLoading && !itemsError && items.length === 0 ? (
                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3 text-sm text-zinc-400">
                    Items отсутствуют.
                  </div>
                ) : null}

                <div className="space-y-2">
                  {filteredItems.map((it) => {
                    const err = String(it.error ?? "").trim();
                    const ok = !err && String(it.status).toLowerCase() === "ok";
                    return (
                      <div
                        key={it.item_id}
                        className={[
                          "rounded-lg border px-3 py-2",
                          err
                            ? "border-red-900/60 bg-red-950/20"
                            : ok
                              ? "border-emerald-900/50 bg-emerald-950/10"
                              : "border-zinc-800 bg-zinc-950/30",
                        ].join(" ")}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="text-sm font-medium text-zinc-100">
                            template #{it.regular_task_id}{" "}
                            <span className="text-xs text-zinc-400">• item #{it.item_id}</span>
                          </div>
                          <div className="text-xs text-zinc-300">{it.status}</div>
                        </div>

                        <div className="mt-1 text-xs text-zinc-400">
                          is_due: <span className="text-zinc-200">{String(it.is_due)}</span>
                          {" • "}
                          created: <span className="text-zinc-200">{it.created_tasks}</span>
                          {" • "}
                          role: <span className="text-zinc-200">{it.executor_role_id ?? "—"}</span>
                          {" • "}
                          period: <span className="text-zinc-200">{it.period_id ?? "—"}</span>
                        </div>

                        {err ? (
                          <div className="mt-2 text-xs text-red-200">
                            {issueLabel(err)}
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>

                {/* raw json */}
                <details className="mt-3 rounded-xl border border-zinc-800 bg-zinc-950/20 p-3">
                  <summary className="cursor-pointer text-sm text-zinc-300">Детали (JSON)</summary>
                  <pre className="mt-2 overflow-auto text-xs text-zinc-200">
                    {JSON.stringify({ run: selectedRun, items }, null, 2)}
                  </pre>
                </details>
              </>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
