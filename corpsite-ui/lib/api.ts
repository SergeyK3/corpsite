// corpsite-ui/lib/api.ts
import { APIError, TaskAction, TaskActionPayload, TaskDetails, TaskListItem } from "./types";

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

function buildUrl(
  path: string,
  query?: Record<string, string | number | boolean | undefined>,
): URL {
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

/**
 * POST /tasks/{id}/actions/{action}
 * - Всегда отправляет JSON (даже пустой объект), чтобы backend не зависел от Content-Length/типов.
 * - Возвращает тело (если есть), иначе null.
 */
export async function apiPostTaskAction(params: {
  devUserId: number;
  taskId: number;
  action: TaskAction;
  payload?: TaskActionPayload;
}): Promise<any> {
  const url = buildUrl(`/tasks/${params.taskId}/actions/${params.action}`);

  const payloadObj = (params.payload ?? {}) as Record<string, any>;

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: buildHeaders(params.devUserId, { "Content-Type": "application/json" }),
    body: JSON.stringify(payloadObj),
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) {
    throw toApiError(res.status, body, {
      method: "POST",
      url: url.toString(),
      taskId: params.taskId,
      action: params.action,
      devUserId: params.devUserId,
      payload: API_TRACE ? payloadObj : undefined,
    });
  }

  return body;
}
