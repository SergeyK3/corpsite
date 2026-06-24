import type {
  APIError,
  MeInfo,
  TaskAction,
  TaskActionPayload,
  TaskDetails,
  TaskListItem,
  TaskScope,
  TasksListResponse,
  RegularTask,
  RegularTaskStatus,
  RegularTasksListResponse,
  TelegramBindCodeResponse,
} from "./types";

import { getSessionAccessToken, logout, setSessionAccessToken } from "./auth";
import { sanitizeBearerToken } from "./bearerToken";
import { formatApiError } from "./i18n";
import { buildUrl as buildApiUrl, resolveApiUrl } from "./apiBase";

function env(name: string, fallback = ""): string {
  const v = process.env[name];
  return (v ?? fallback).toString().trim();
}

function truthyEnv(name: string): boolean {
  const v = env(name, "").toLowerCase();
  return v === "1" || v === "true" || v === "yes" || v === "y" || v === "on";
}

const API_TRACE = truthyEnv("NEXT_PUBLIC_API_TRACE");

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
    message: formatApiError(status, body),
    details: body,
  };

  if (API_TRACE && meta) {
    (err as any).meta = meta;
  }

  return err;
}

export { resolveApiUrl } from "./apiBase";

export function buildUrl(
  path: string,
  query?: Record<string, string | number | boolean | undefined | null>,
): URL {
  return buildApiUrl(path, query);
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
  const url = buildUrl(path, opts?.query).toString();

  const headers: Record<string, string> = {
    ...(opts?.headers ?? {}),
  };

  let bodyStr: string | undefined = undefined;
  if (opts?.body !== undefined) {
    headers["Content-Type"] = headers["Content-Type"] ?? "application/json";
    bodyStr = JSON.stringify(opts.body);
  }

  const res = await fetch(url, {
    method,
    headers: buildHeaders(headers, { noAuth: !!opts?.noAuth }),
    body: bodyStr,
    cache: "no-store",
  });

  const body = await readJsonSafe(res);

  if (!res.ok) {
    handleAuthFailureIfNeeded(res.status);
    throw toApiError(res.status, body, { method, url });
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
  const url = resolveApiUrl("/auth/login");

  const res = await fetch(url, {
    method: "POST",
    headers: buildHeaders({ "Content-Type": "application/json" }, { noAuth: true }),
    body: JSON.stringify({ login, password }),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);

  if (!res.ok) {
    throw toApiError(res.status, body, { method: "POST", url });
  }

  const token = sanitizeBearerToken(body?.access_token);
  if (!token) {
    throw toApiError(
      500,
      { message: "Backend did not return access_token" },
      { method: "POST", url },
    );
  }

  setSessionAccessToken(token);

  return body;
}

export type { TelegramBindCodeResponse } from "./types";

export async function apiAuthMe(): Promise<MeInfo> {
  return apiFetchJson<MeInfo>("/auth/me");
}

export async function apiCreateTelegramBindCode(): Promise<TelegramBindCodeResponse> {
  return apiFetchJson<TelegramBindCodeResponse>("/me/tg-bind-code", {
    method: "POST",
  });
}

/* ============================================================
 * TASKS
 * ============================================================ */

export async function apiGetTasks(params: {
  scope?: TaskScope;
  limit?: number;
  offset?: number;
  executor_role_id?: number;
  org_group_id?: number;
  org_unit_id?: number;
}): Promise<TasksListResponse> {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;

  const body = await apiFetchJson<any>("/tasks", {
    query: {
      scope: params.scope ?? "mine",
      limit,
      offset,
      executor_role_id: params.executor_role_id ?? undefined,
      org_group_id: params.org_group_id ?? undefined,
      org_unit_id: params.org_unit_id ?? undefined,
    },
  });

  const items = normalizeList<TaskListItem>(body);

  return {
    scope: body?.scope === "team" ? "team" : "mine",
    total: typeof body?.total === "number" ? body.total : items.length,
    limit: typeof body?.limit === "number" ? body.limit : limit,
    offset: typeof body?.offset === "number" ? body.offset : offset,
    items,
  };
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

export async function apiPatchRegularTask(params: {
  regularTaskId: number;
  payload: Record<string, any>;
}): Promise<any> {
  return apiFetchJson<any>(`/regular-tasks/${params.regularTaskId}`, {
    method: "PATCH",
    body: params.payload ?? {},
  });
}

export async function apiActivateRegularTask(params: { regularTaskId: number }): Promise<any> {
  return apiFetchJson<any>(`/regular-tasks/${params.regularTaskId}/activate`, { method: "POST" });
}

export async function apiDeactivateRegularTask(params: { regularTaskId: number }): Promise<any> {
  return apiFetchJson<any>(`/regular-tasks/${params.regularTaskId}/deactivate`, { method: "POST" });
}

export async function apiDeleteRegularTask(params: { regularTaskId: number }): Promise<any> {
  return apiFetchJson<any>(`/regular-tasks/${params.regularTaskId}`, { method: "DELETE" });
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
 * REGULAR TASKS CATCH-UP (admin internal)
 * ============================================================ */

export type CatchUpPreset = "past_week" | "past_month" | "manual";

export type CatchUpRegularTasksParams = {
  dry_run: boolean;
  preset: CatchUpPreset;
  run_for_date?: string;
  schedule_type?: string;
  org_group_id?: number;
  org_unit_id?: number;
  executor_role_id?: number;
  regular_task_id?: number;
};

export type CatchUpRegularTasksResult = {
  run_id: number;
  dry_run: boolean;
  resolved?: {
    preset?: string;
    run_for_date?: string;
    schedule_type?: string | null;
    org_group_id?: number | null;
    org_unit_id?: number | null;
    executor_role_id?: number | null;
    regular_task_id?: number | null;
    templates_in_scope?: number;
  };
  stats?: {
    templates_total?: number;
    templates_due?: number;
    created?: number;
    deduped?: number;
    errors?: number;
  };
};

export async function apiCatchUpRegularTasks(
  params: CatchUpRegularTasksParams,
): Promise<CatchUpRegularTasksResult> {
  return apiFetchJson<CatchUpRegularTasksResult>("/internal/regular-tasks/catch-up", {
    method: "POST",
    body: params,
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

export async function apiGetRegularTaskRuns(): Promise<RegularTaskRun[]> {
  const body = await apiFetchJson<any>("/regular-task-runs");
  return normalizeList<RegularTaskRun>(body);
}

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
  task?: RegularTaskRunItemTaskOutcome | null;
};

export type RegularTaskRunItemTaskOutcome = {
  task_id: number;
  resolved: boolean;
  status_code?: string | null;
  status_name_ru?: string | null;
  due_date?: string | null;
  is_overdue: boolean;
  lifecycle?: string | null;
};

export type RegularTaskRunOutcomeCounts = {
  linked: number;
  done: number;
  in_progress: number;
  overdue: number;
  archived: number;
  unlinked: number;
  other: number;
};

export type RegularTaskRunOutcome = {
  run_id: number;
  period_label?: string | null;
  counts: RegularTaskRunOutcomeCounts;
};

export type RegularTaskRunItemsEnvelope = {
  run_id: number;
  items: RegularTaskRunItem[];
  outcome: RegularTaskRunOutcome;
};

export function normalizeRegularTaskRunItemsList(body: any): RegularTaskRunItem[] {
  return normalizeList<RegularTaskRunItem>(body);
}

export function parseRegularTaskRunItemsResponse(body: any): {
  items: RegularTaskRunItem[];
  outcome: RegularTaskRunOutcome | null;
} {
  if (Array.isArray(body)) {
    return { items: body as RegularTaskRunItem[], outcome: null };
  }
  if (body?.items && Array.isArray(body.items)) {
    return {
      items: body.items as RegularTaskRunItem[],
      outcome: (body.outcome as RegularTaskRunOutcome | undefined) ?? null,
    };
  }
  return { items: [], outcome: null };
}

export async function apiGetRegularTaskRunItems(params: {
  run_id: number;
  include_outcome?: boolean;
}): Promise<{ items: RegularTaskRunItem[]; outcome: RegularTaskRunOutcome | null }> {
  const body = await apiFetchJson<any>(`/regular-task-runs/${params.run_id}/items`, {
    query: params.include_outcome ? { include_outcome: true } : undefined,
  });
  return parseRegularTaskRunItemsResponse(body);
}