import { APIError, TaskAction, TaskActionPayload, TaskDetails, TaskListItem } from "./types";

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

function toApiError(status: number, body: any): APIError {
  return {
    status,
    code: body?.code,
    message: body?.message ?? body?.detail ?? body?.error ?? "Request failed",
    details: body,
  };
}

export async function apiGetTasks(params: {
  devUserId: number;
  limit?: number;
  offset?: number;
}): Promise<TaskListItem[]> {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;

  const url = new URL("/tasks", API_BASE_URL);
  url.searchParams.set("limit", String(limit));
  url.searchParams.set("offset", String(offset));

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: { "X-User-Id": String(params.devUserId) },
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body);

  if (Array.isArray(body)) return body;
  if (body?.items && Array.isArray(body.items)) return body.items;

  return [];
}

export async function apiGetTask(params: { devUserId: number; taskId: number }): Promise<TaskDetails> {
  const url = new URL(`/tasks/${params.taskId}`, API_BASE_URL);

  const res = await fetch(url.toString(), {
    method: "GET",
    headers: { "X-User-Id": String(params.devUserId) },
    cache: "no-store",
  });

  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body);

  return body as TaskDetails;
}

export async function apiPostTaskAction(params: {
  devUserId: number;
  taskId: number;
  action: TaskAction;
  payload: TaskActionPayload;
}): Promise<any> {
  const url = new URL(`/tasks/${params.taskId}/actions/${params.action}`, API_BASE_URL);

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": String(params.devUserId),
    },
    body: JSON.stringify(params.payload ?? {}),
  });

  const body = await readJsonSafe(res);
  if (!res.ok) throw toApiError(res.status, body);

  return body;
}
