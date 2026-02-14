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

function env(name: string, fallback = ""): string {
  const v = process.env[name];
  return (v ?? fallback).toString().trim();
}

const API_BASE_URL = env("NEXT_PUBLIC_API_BASE_URL", "http://127.0.0.1:8000");

/**
 * Включает больше диагностических данных в ошибках (без console.log).
 * Управляется env: NEXT_PUBLIC_API_TRACE=1|true|yes|on
 */
function truthyEnv(name: string): boolean {
  const v = env(name, "").toLowerCase();
  return v === "1" || v === "true" || v === "yes" || v === "y" || v === "on";
}

const API_TRACE = truthyEnv("NEXT_PUBLIC_API_TRACE");

// единые ключи sessionStorage
const AUTH_ACCESS_TOKEN_KEY = "access_token";
const SESSION_USER_ID_KEY = "user_id";

function readAccessToken(): string {
  if (typeof window === "undefined") return "";
  try {
    return (window.sessionStorage.getItem(AUTH_ACCESS_TOKEN_KEY) ?? "").toString().trim();
  } catch {
    return "";
  }
}

function readSessionUserId(): string {
  if (typeof window === "undefined") return "";
  try {
    const raw = (window.sessionStorage.getItem(SESSION_USER_ID_KEY) ?? "").toString().trim();
    const n = Number(raw);
    if (Number.isFinite(n) && n > 0) return String(Math.floor(n));
  } catch {
    // ignore
  }
  return "";
}

function setAccessToken(token: string): void {
  if (typeof window === "undefined") return;
  const t = (token ?? "").toString().trim();
  if (!t) return;
  try {
    window.sessionStorage.setItem(AUTH_ACCESS_TOKEN_KEY, t);
  } catch {
    // ignore
  }
}

export function clearAccessToken(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(AUTH_ACCESS_TOKEN_KEY);
  } catch {
    // ignore
  }
}

export function isAuthed(): boolean {
  return !!readAccessToken();
}

async function readJsonSafe(res: Response): Promise<any> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

function toApiError(status: number, body: any, meta?: Record<string, any>): APIError {
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

function buildUrl(
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

/**
 * JWT-only headers builder + X-User-Id (если есть в sessionStorage).
 * Для /auth/login можно отключить Authorization через opts.noAuth.
 */
function buildHeaders(
  extra?: Record<string, string>,
  opts?: { noAuth?: boolean },
): HeadersInit {
  const tok = opts?.noAuth ? "" : readAccessToken();
  const uid = readSessionUserId();

  const headers: Record<string, string> = {
    ...(extra ?? {}),
  };

  if (tok) {
    headers["Authorization"] = `Bearer ${tok}`;
  }

  if (uid) {
    headers["X-User-Id"] = uid;
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

function handleAuthFailureIfNeeded(status: number): void {
  if (status === 401) {
    clearAccessToken();
  }
}

/* ============================================================
 * AUTH
 * ============================================================ */

export async function apiAuthLogin(params: {
  login: string;
  password: string;
}): Promise<{ access_token: string; token_type: string }> {
  const login = (params.login ?? "").toString().trim().toLowerCase();
  const password = (params.password ?? "").toString();

  const url = buildUrl("/auth/login");

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }, { noAuth: true }),
    body: JSON.stringify({ login, password }),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    handleAuthFailureIfNeeded(res.status);
    throw toApiError(res.status, body, {
      method: "POST",
      url: url.toString(),
      login: API_TRACE ? login : undefined,
    });
  }

  const token = (body?.access_token ?? "").toString().trim();
  if (!token) {
    throw toApiError(
      500,
      { message: "Backend did not return access_token" },
      { method: "POST", url: url.toString() },
    );
  }

  setAccessToken(token);
  return body as any;
}

export async function apiAuthMe(): Promise<any> {
  const url = buildUrl("/auth/me");

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: buildHeaders(),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    handleAuthFailureIfNeeded(res.status);
    throw toApiError(res.status, body, { method: "GET", url: url.toString() });
  }

  return body;
}

/* ============================================================
 * TASKS
 * ============================================================ */

export async function apiGetTasks(params: {
  devUserId?: number;
  limit?: number;
  offset?: number;
  executor_role_id?: number;
}): Promise<TaskListItem[]> {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;

  const url = buildUrl("/tasks", {
    limit,
    offset,
    executor_role_id: params.executor_role_id ?? undefined,
  });

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: buildHeaders(),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    handleAuthFailureIfNeeded(res.status);
    throw toApiError(res.status, body, {
      method: "GET",
      url: url.toString(),
      limit,
      offset,
      executor_role_id: params.executor_role_id ?? null,
      devUserId: params.devUserId ?? null,
    });
  }

  return normalizeList<TaskListItem>(body);
}

export async function apiGetTask(params: {
  devUserId?: number;
  taskId: number;
  includeArchived?: boolean;
}): Promise<TaskDetails> {
  const url = buildUrl(`/tasks/${params.taskId}`, {
    include_archived: !!params.includeArchived,
  });

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: buildHeaders(),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    handleAuthFailureIfNeeded(res.status);
    throw toApiError(res.status, body, {
      method: "GET",
      url: url.toString(),
      taskId: params.taskId,
      devUserId: params.devUserId ?? null,
    });
  }

  return body as TaskDetails;
}

export async function apiPostTaskAction(params: {
  devUserId?: number;
  taskId: number;
  action: TaskAction;
  payload?: TaskActionPayload;
}): Promise<any> {
  const payloadObj = (params.payload ?? {}) as Record<string, any>;

  const currentComment = pickString(payloadObj, ["current_comment", "comment"]);
  const reportLink = pickString(payloadObj, ["report_link", "reportLink", "link", "url"]);
  const reason = pickString(payloadObj, ["reason", "current_comment", "comment"]);

  let url: URL;
  let body: string | undefined;

  if (params.action === "report") {
    url = buildUrl(`/tasks/${params.taskId}/report`);
    const out: Record<string, any> = { report_link: reportLink };
    if (currentComment) out.current_comment = currentComment;
    body = JSON.stringify(out);
  } else if (params.action === "approve") {
    url = buildUrl(`/tasks/${params.taskId}/approve`);
    const out: Record<string, any> = {};
    if (reason) out.reason = reason;
    body = JSON.stringify(out);
  } else if (params.action === "reject") {
    url = buildUrl(`/tasks/${params.taskId}/reject`);
    const out: Record<string, any> = {};
    if (reason) out.reason = reason;
    body = JSON.stringify(out);
  } else if (params.action === "archive") {
    url = buildUrl(`/tasks/${params.taskId}/archive`);
    const out: Record<string, any> = {};
    if (reason) out.reason = reason;
    body = JSON.stringify(out);
  } else {
    url = buildUrl(`/tasks/${params.taskId}/approve`);
    const out: Record<string, any> = {};
    if (reason) out.reason = reason;
    body = JSON.stringify(out);
  }

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }),
    body,
    cache: "no-store",
  });

  const resBody = await readJsonSafe(res);
  if (!res.ok) {
    handleAuthFailureIfNeeded(res.status);
    throw toApiError(res.status, resBody, {
      method: "POST",
      url: url.toString(),
      taskId: params.taskId,
      action: params.action,
      devUserId: params.devUserId ?? null,
      payload: API_TRACE ? payloadObj : undefined,
    });
  }

  return resBody;
}

/* ============================================================
 * REGULAR TASKS
 * ============================================================ */

export async function apiGetRegularTasks(params: {
  devUserId?: number;
  status?: RegularTaskStatus;
  q?: string;
  schedule_type?: string;
  executor_role_id?: number;
  limit?: number;
  offset?: number;
}): Promise<RegularTask[]> {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;

  const url = buildUrl("/regular-tasks", {
    status: params.status ?? "active",
    q: params.q ?? undefined,
    schedule_type: params.schedule_type ?? undefined,
    executor_role_id: params.executor_role_id ?? undefined,
    limit,
    offset,
  });

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: buildHeaders(),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    handleAuthFailureIfNeeded(res.status);
    throw toApiError(res.status, body, {
      method: "GET",
      url: url.toString(),
      devUserId: params.devUserId ?? null,
    });
  }

  return normalizeList<RegularTask>(body);
}

export async function apiGetRegularTask(params: {
  devUserId?: number;
  regularTaskId: number;
}): Promise<RegularTask> {
  const url = buildUrl(`/regular-tasks/${params.regularTaskId}`);

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: buildHeaders(),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    handleAuthFailureIfNeeded(res.status);
    throw toApiError(res.status, body, {
      method: "GET",
      url: url.toString(),
      regularTaskId: params.regularTaskId,
      devUserId: params.devUserId ?? null,
    });
  }

  return body as RegularTask;
}

export async function apiCreateRegularTask(params: {
  devUserId?: number;
  payload: Record<string, any>;
}): Promise<any> {
  const url = buildUrl("/regular-tasks");

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(params.payload ?? {}),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    handleAuthFailureIfNeeded(res.status);
    throw toApiError(res.status, body, {
      method: "POST",
      url: url.toString(),
      devUserId: params.devUserId ?? null,
      payload: API_TRACE ? params.payload : undefined,
    });
  }

  return body;
}

export async function apiPatchRegularTask(params: {
  devUserId?: number;
  regularTaskId: number;
  payload: Record<string, any>;
}): Promise<any> {
  const url = buildUrl(`/regular-tasks/${params.regularTaskId}`);

  const res = await fetch(url.toString(), {
    method: "PATCH",
    headers: buildHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(params.payload ?? {}),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    handleAuthFailureIfNeeded(res.status);
    throw toApiError(res.status, body, {
      method: "PATCH",
      url: url.toString(),
      regularTaskId: params.regularTaskId,
      devUserId: params.devUserId ?? null,
      payload: API_TRACE ? params.payload : undefined,
    });
  }

  return body;
}

export async function apiActivateRegularTask(params: {
  devUserId?: number;
  regularTaskId: number;
}): Promise<any> {
  const url = buildUrl(`/regular-tasks/${params.regularTaskId}/activate`);

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: buildHeaders(),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    handleAuthFailureIfNeeded(res.status);
    throw toApiError(res.status, body, {
      method: "POST",
      url: url.toString(),
      regularTaskId: params.regularTaskId,
      devUserId: params.devUserId ?? null,
    });
  }

  return body;
}

export async function apiDeactivateRegularTask(params: {
  devUserId?: number;
  regularTaskId: number;
}): Promise<any> {
  const url = buildUrl(`/regular-tasks/${params.regularTaskId}/deactivate`);

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: buildHeaders(),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    handleAuthFailureIfNeeded(res.status);
    throw toApiError(res.status, body, {
      method: "POST",
      url: url.toString(),
      regularTaskId: params.regularTaskId,
      devUserId: params.devUserId ?? null,
    });
  }

  return body;
}

export async function apiGetRegularTasksRaw(params: {
  devUserId?: number;
  status?: RegularTaskStatus;
  q?: string;
  schedule_type?: string;
  executor_role_id?: number;
  limit?: number;
  offset?: number;
}): Promise<RegularTasksListResponse | RegularTask[]> {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;

  const url = buildUrl("/regular-tasks", {
    status: params.status ?? "active",
    q: params.q ?? undefined,
    schedule_type: params.schedule_type ?? undefined,
    executor_role_id: params.executor_role_id ?? undefined,
    limit,
    offset,
  });

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: buildHeaders(),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    handleAuthFailureIfNeeded(res.status);
    throw toApiError(res.status, body, {
      method: "GET",
      url: url.toString(),
      devUserId: params.devUserId ?? null,
    });
  }

  return body as any;
}
