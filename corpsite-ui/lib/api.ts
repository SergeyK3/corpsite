// FILE: corpsite-ui/lib/api.ts
import type {
  APIError,
  TaskAction,
  TaskActionPayload,
  TaskDetails,
  TaskListItem,
  RegularTask,
  RegularTaskStatus,
  RegularTasksListResponse,
} from "./types";

import { getSessionAccessToken, logout, setSessionAccessToken } from "./auth";

function env(name: string, fallback = ""): string {
  const v = process.env[name];
  return (v ?? fallback).toString().trim();
}

const API_BASE_URL = env("NEXT_PUBLIC_API_BASE_URL", "http://127.0.0.1:8000");

function truthyEnv(name: string): boolean {
  const v = env(name, "").toLowerCase();
  return v === "1" || v === "true" || v === "yes" || v === "y" || v === "on";
}

const API_TRACE = truthyEnv("NEXT_PUBLIC_API_TRACE");

/* ============================================================
 * TOKEN SANITIZATION (critical for "Failed to fetch")
 * ============================================================ */

/**
 * Удаляет управляющие символы (включая CR/LF), BOM/нулевой символ,
 * лишние пробелы, и убирает "Bearer " если он уже внутри токена.
 *
 * Причина: если в Authorization попадает \r или \n — браузер не отправляет запрос
 * и UI получает "Failed to fetch".
 */
function sanitizeBearerToken(raw: any): string {
  if (!raw) return "";
  let s = String(raw);

  // убрать BOM (U+FEFF) и NUL
  s = s.replace(/\uFEFF/g, "").replace(/\u0000/g, "");

  // убрать ВСЕ ASCII control chars: 0x00-0x1F и 0x7F (включая \r \n \t)
  s = s.replace(/[\u0000-\u001F\u007F]/g, "");

  s = s.trim();

  // если токен уже содержит "Bearer " — вычистим, чтобы не получить "Bearer Bearer ..."
  if (/^bearer\s+/i.test(s)) {
    s = s.replace(/^bearer\s+/i, "").trim();
  }

  return s;
}

/* ============================================================
 * HELPERS (exported for shared API clients)
 * ============================================================ */

export async function readJsonSafe(res: Response): Promise<any> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

export function toApiError(status: number, body: any, meta?: Record<string, any>): APIError {
  const err: APIError = {
    status,
    code: body?.code,
    message: body?.message ?? body?.detail ?? body?.error ?? "Request failed",
    details: body,
  };

  if (API_TRACE && meta) {
    (err as any).meta = meta;
  }

  return err;
}

export function buildUrl(
  path: string,
  query?: Record<string, string | number | boolean | undefined | null>,
): URL {
  const url = new URL(path, API_BASE_URL);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null) continue;
      url.searchParams.set(k, String(v));
    }
  }
  return url;
}

export function buildHeaders(
  extra?: Record<string, string>,
  opts?: { noAuth?: boolean },
): HeadersInit {
  const rawTok = opts?.noAuth ? "" : getSessionAccessToken();
  const tok = sanitizeBearerToken(rawTok);

  const headers: Record<string, string> = {
    ...(extra ?? {}),
  };

  if (tok) {
    headers["Authorization"] = `Bearer ${tok}`;
  }

  return headers;
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

function normalizeList<T>(body: any): T[] {
  if (Array.isArray(body)) return body as T[];
  if (body?.items && Array.isArray(body.items)) return body.items as T[];
  return [];
}

export function handleAuthFailureIfNeeded(status: number): void {
  if (status === 401) {
    logout();
  }
}

/**
 * Универсальный fetch JSON с Bearer-токеном (один источник правды).
 * Используй его в directory/* клиентах вместо прямого fetch().
 */
export async function apiFetchJson<T>(
  path: string,
  opts?: {
    method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
    query?: Record<string, string | number | boolean | undefined | null>;
    body?: any;
    noAuth?: boolean;
    headers?: Record<string, string>;
  },
): Promise<T> {
  const method = opts?.method ?? "GET";
  const url = buildUrl(path, opts?.query);

  const headers: Record<string, string> = {
    ...(opts?.headers ?? {}),
  };

  let bodyStr: string | undefined = undefined;
  if (opts?.body !== undefined) {
    headers["Content-Type"] = headers["Content-Type"] ?? "application/json";
    bodyStr = JSON.stringify(opts.body);
  }

  const res = await fetch(url.toString(), {
    method,
    headers: buildHeaders(headers, { noAuth: !!opts?.noAuth }),
    body: bodyStr,
    cache: "no-store",
  });

  const body = await readJsonSafe(res);

  if (!res.ok) {
    handleAuthFailureIfNeeded(res.status);
    throw toApiError(res.status, body, { method, url: url.toString() });
  }

  return body as T;
}

/* ============================================================
 * AUTH
 * ============================================================ */

export async function apiAuthLogin(params: {
  login: string;
  password: string;
}): Promise<{
  access_token: string;
  token_type: string;
}> {
  const login = (params.login ?? "").toString().trim().toLowerCase();
  const password = (params.password ?? "").toString();

  const body = await apiFetchJson<any>("/auth/login", {
    method: "POST",
    noAuth: true,
    body: { login, password },
  });

  // на вход в storage кладём уже нормализованный токен
  const token = sanitizeBearerToken(body?.access_token);
  if (!token) {
    throw toApiError(
      500,
      { message: "Backend did not return access_token" },
      { method: "POST", url: "/auth/login" },
    );
  }

  setSessionAccessToken(token);

  // возвращаем body как есть (контракт с UI)
  return body;
}

export async function apiAuthMe(): Promise<any> {
  return apiFetchJson<any>("/auth/me");
}

/* ============================================================
 * TASKS
 * ============================================================ */

export async function apiGetTasks(params: {
  limit?: number;
  offset?: number;
  executor_role_id?: number;
}): Promise<TaskListItem[]> {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;

  const body = await apiFetchJson<any>("/tasks", {
    query: {
      limit,
      offset,
      executor_role_id: params.executor_role_id ?? undefined,
    },
  });

  return normalizeList<TaskListItem>(body);
}

export async function apiGetTask(params: {
  taskId: number;
  includeArchived?: boolean;
}): Promise<TaskDetails> {
  return apiFetchJson<TaskDetails>(`/tasks/${params.taskId}`, {
    query: { include_archived: !!params.includeArchived },
  });
}

export async function apiPostTaskAction(params: {
  taskId: number;
  action: TaskAction;
  payload?: TaskActionPayload;
}): Promise<any> {
  const payloadObj = (params.payload ?? {}) as Record<string, any>;

  const currentComment = pickString(payloadObj, ["current_comment", "comment"]);
  const reportLink = pickString(payloadObj, ["report_link", "reportLink", "link", "url"]);
  const reason = pickString(payloadObj, ["reason", "current_comment", "comment"]);

  if (params.action === "report") {
    const out: Record<string, any> = { report_link: reportLink };
    if (currentComment) out.current_comment = currentComment;
    return apiFetchJson<any>(`/tasks/${params.taskId}/report`, { method: "POST", body: out });
  }

  const out: Record<string, any> = {};
  if (reason) out.reason = reason;
  return apiFetchJson<any>(`/tasks/${params.taskId}/${params.action}`, {
    method: "POST",
    body: out,
  });
}

/* ============================================================
 * REGULAR TASKS (existing CRUD)
 * ============================================================ */

export async function apiGetRegularTasks(params: {
  status?: RegularTaskStatus;
  q?: string;
  schedule_type?: string;
  executor_role_id?: number;
  limit?: number;
  offset?: number;
}): Promise<RegularTask[]> {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;

  const body = await apiFetchJson<any>("/regular-tasks", {
    query: {
      status: params.status ?? "active",
      q: params.q ?? undefined,
      schedule_type: params.schedule_type ?? undefined,
      executor_role_id: params.executor_role_id ?? undefined,
      limit,
      offset,
    },
  });

  return normalizeList<RegularTask>(body);
}

export async function apiGetRegularTask(params: { regularTaskId: number }): Promise<RegularTask> {
  return apiFetchJson<RegularTask>(`/regular-tasks/${params.regularTaskId}`);
}

export async function apiCreateRegularTask(params: { payload: Record<string, any> }): Promise<any> {
  return apiFetchJson<any>("/regular-tasks", { method: "POST", body: params.payload ?? {} });
}

export async function apiPatchRegularTask(params: { regularTaskId: number; payload: Record<string, any> }): Promise<any> {
  return apiFetchJson<any>(`/regular-tasks/${params.regularTaskId}`, { method: "PATCH", body: params.payload ?? {} });
}

export async function apiActivateRegularTask(params: { regularTaskId: number }): Promise<any> {
  return apiFetchJson<any>(`/regular-tasks/${params.regularTaskId}/activate`, { method: "POST" });
}

export async function apiDeactivateRegularTask(params: { regularTaskId: number }): Promise<any> {
  return apiFetchJson<any>(`/regular-tasks/${params.regularTaskId}/deactivate`, { method: "POST" });
}

export async function apiGetRegularTasksRaw(params: {
  status?: RegularTaskStatus;
  q?: string;
  schedule_type?: string;
  executor_role_id?: number;
  limit?: number;
  offset?: number;
}): Promise<RegularTasksListResponse | RegularTask[]> {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;

  return apiFetchJson<any>("/regular-tasks", {
    query: {
      status: params.status ?? "active",
      q: params.q ?? undefined,
      schedule_type: params.schedule_type ?? undefined,
      executor_role_id: params.executor_role_id ?? undefined,
      limit,
      offset,
    },
  });
}

/* ============================================================
 * REGULAR TASK RUNS (new public read endpoints)
 * ============================================================ */

export type RegularTaskRun = {
  run_id: number;
  started_at: string;
  finished_at?: string | null;
  status: string;
  stats?: any;
  errors?: any;
};

export type RegularTaskRunItem = {
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

export async function apiGetRegularTaskRuns(): Promise<RegularTaskRun[]> {
  const body = await apiFetchJson<any>("/regular-task-runs");
  return normalizeList<RegularTaskRun>(body);
}

export async function apiGetRegularTaskRunItems(params: { run_id: number }): Promise<RegularTaskRunItem[]> {
  const body = await apiFetchJson<any>(`/regular-task-runs/${params.run_id}/items`);
  return normalizeList<RegularTaskRunItem>(body);
}