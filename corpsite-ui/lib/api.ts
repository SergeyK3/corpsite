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

/**
 * Умеет читать JSON/текст и не падать при пустом теле.
 * Если тело не JSON — возвращает { message: <text> }.
 */
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

function buildUrl(path: string, query?: Record<string, string | number | boolean | undefined | null>): URL {
  const url = new URL(path, API_BASE_URL);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v === undefined || v === null) continue;
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

/* ============================================================
 * TASKS
 * ============================================================ */

export async function apiGetTasks(params: { devUserId: number; limit?: number; offset?: number }): Promise<TaskListItem[]> {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;

  const url = buildUrl("/tasks", { limit, offset });

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: buildHeaders(params.devUserId),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, {
      method: "GET",
      url: url.toString(),
      limit,
      offset,
      devUserId: params.devUserId,
    });
  }

  return normalizeList<TaskListItem>(body);
}

export async function apiGetTask(params: {
  devUserId: number;
  taskId: number;
  includeArchived?: boolean;
}): Promise<TaskDetails> {
  const url = buildUrl(`/tasks/${params.taskId}`, {
    include_archived: !!params.includeArchived,
  });

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: buildHeaders(params.devUserId),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, {
      method: "GET",
      url: url.toString(),
      taskId: params.taskId,
      devUserId: params.devUserId,
    });
  }

  return body as TaskDetails;
}

/**
 * Backend endpoints:
 * - POST /tasks/{id}/report    { report_link, current_comment? }
 * - POST /tasks/{id}/approve   { reason? }
 * - POST /tasks/{id}/reject    { reason? }
 * - POST /tasks/{id}/archive   { reason? }
 */
export async function apiPostTaskAction(params: {
  devUserId: number;
  taskId: number;
  action: TaskAction;
  payload?: TaskActionPayload;
}): Promise<any> {
  const payloadObj = (params.payload ?? {}) as Record<string, any>;

  const currentComment = pickString(payloadObj, ["current_comment", "comment"]);
  const reportLink = pickString(payloadObj, ["report_link", "reportLink", "link", "url"]);
  const reason = pickString(payloadObj, ["reason", "current_comment", "comment"]); // reason по умолчанию можно брать из comment

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
    // safety fallback: approve
    url = buildUrl(`/tasks/${params.taskId}/approve`);
    const out: Record<string, any> = {};
    if (reason) out.reason = reason;
    body = JSON.stringify(out);
  }

  const headers = buildHeaders(params.devUserId, { "Content-Type": "application/json" });

  const res = await fetch(url.toString(), {
    method: "POST",
    headers,
    body,
    cache: "no-store",
  });

  const resBody = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, resBody, {
      method: "POST",
      url: url.toString(),
      taskId: params.taskId,
      action: params.action,
      devUserId: params.devUserId,
      payload: API_TRACE ? payloadObj : undefined,
    });
  }

  return resBody;
}

/* ============================================================
 * REGULAR TASKS
 * ============================================================ */

export async function apiGetRegularTasks(params: {
  devUserId: number;
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
    headers: buildHeaders(params.devUserId),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, {
      method: "GET",
      url: url.toString(),
      devUserId: params.devUserId,
      query: API_TRACE
        ? {
            status: params.status ?? "active",
            q: params.q ?? null,
            schedule_type: params.schedule_type ?? null,
            executor_role_id: params.executor_role_id ?? null,
            limit,
            offset,
          }
        : undefined,
    });
  }

  return normalizeList<RegularTask>(body);
}

export async function apiGetRegularTask(params: { devUserId: number; regularTaskId: number }): Promise<RegularTask> {
  const url = buildUrl(`/regular-tasks/${params.regularTaskId}`);

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: buildHeaders(params.devUserId),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, {
      method: "GET",
      url: url.toString(),
      regularTaskId: params.regularTaskId,
      devUserId: params.devUserId,
    });
  }

  return body as RegularTask;
}

export async function apiCreateRegularTask(params: { devUserId: number; payload: Record<string, any> }): Promise<any> {
  const url = buildUrl("/regular-tasks");

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: buildHeaders(params.devUserId, { "Content-Type": "application/json" }),
    body: JSON.stringify(params.payload ?? {}),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, {
      method: "POST",
      url: url.toString(),
      devUserId: params.devUserId,
      payload: API_TRACE ? params.payload : undefined,
    });
  }

  return body;
}

export async function apiPatchRegularTask(params: {
  devUserId: number;
  regularTaskId: number;
  payload: Record<string, any>;
}): Promise<any> {
  const url = buildUrl(`/regular-tasks/${params.regularTaskId}`);

  const res = await fetch(url.toString(), {
    method: "PATCH",
    headers: buildHeaders(params.devUserId, { "Content-Type": "application/json" }),
    body: JSON.stringify(params.payload ?? {}),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, {
      method: "PATCH",
      url: url.toString(),
      regularTaskId: params.regularTaskId,
      devUserId: params.devUserId,
      payload: API_TRACE ? params.payload : undefined,
    });
  }

  return body;
}

export async function apiActivateRegularTask(params: { devUserId: number; regularTaskId: number }): Promise<any> {
  const url = buildUrl(`/regular-tasks/${params.regularTaskId}/activate`);

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: buildHeaders(params.devUserId),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, {
      method: "POST",
      url: url.toString(),
      regularTaskId: params.regularTaskId,
      devUserId: params.devUserId,
    });
  }

  return body;
}

export async function apiDeactivateRegularTask(params: { devUserId: number; regularTaskId: number }): Promise<any> {
  const url = buildUrl(`/regular-tasks/${params.regularTaskId}/deactivate`);

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: buildHeaders(params.devUserId),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, {
      method: "POST",
      url: url.toString(),
      regularTaskId: params.regularTaskId,
      devUserId: params.devUserId,
    });
  }

  return body;
}

/**
 * Если вдруг понадобится сырое тело list-ответа (total/limit/offset),
 * оставляю отдельную функцию, но UI может и не использовать её.
 */
export async function apiGetRegularTasksRaw(params: {
  devUserId: number;
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
    headers: buildHeaders(params.devUserId),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, {
      method: "GET",
      url: url.toString(),
      devUserId: params.devUserId,
    });
  }

  return body as any;
}
