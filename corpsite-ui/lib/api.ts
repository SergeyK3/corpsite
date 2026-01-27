// FILE: corpsite-ui/lib/api.ts
import type { APIError, TaskAction, TaskActionPayload, TaskDetails, TaskListItem } from "./types";

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

export async function apiGetTasks(params: {
  devUserId: number;
  limit?: number;
  offset?: number;
}): Promise<TaskListItem[]> {
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

  if (Array.isArray(body)) return body as TaskListItem[];
  if (body?.items && Array.isArray(body.items)) return body.items as TaskListItem[];

  return [];
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

/**
 * Backend endpoints:
 * - POST /tasks/{id}/report   { report_link, current_comment? }
 * - POST /tasks/{id}/approve  { approve: true|false, current_comment? }
 * - DELETE /tasks/{id}        (archive)
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

  let method: "POST" | "DELETE" = "POST";
  let url: URL;
  let body: string | undefined = undefined;

  if (params.action === "report") {
    url = buildUrl(`/tasks/${params.taskId}/report`);
    const out: Record<string, any> = {
      report_link: reportLink,
    };
    if (currentComment) out.current_comment = currentComment;
    body = JSON.stringify(out);
  } else if (params.action === "approve" || params.action === "reject") {
    url = buildUrl(`/tasks/${params.taskId}/approve`);
    const out: Record<string, any> = {
      approve: params.action === "approve",
    };
    if (currentComment) out.current_comment = currentComment;
    body = JSON.stringify(out);
  } else if (params.action === "archive") {
    url = buildUrl(`/tasks/${params.taskId}`);
    method = "DELETE";
  } else {
    url = buildUrl(`/tasks/${params.taskId}/approve`);
    const out: Record<string, any> = { approve: true };
    if (currentComment) out.current_comment = currentComment;
    body = JSON.stringify(out);
  }

  const headers =
    method === "POST"
      ? buildHeaders(params.devUserId, { "Content-Type": "application/json" })
      : buildHeaders(params.devUserId);

  const res = await fetch(url.toString(), {
    method,
    headers,
    body,
    cache: "no-store",
  });

  const resBody = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, resBody, {
      method,
      url: url.toString(),
      taskId: params.taskId,
      action: params.action,
      devUserId: params.devUserId,
      payload: API_TRACE ? payloadObj : undefined,
    });
  }

  return resBody;
}
