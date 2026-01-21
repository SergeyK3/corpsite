// FILE: corpsite-ui/app/directory/org-units/_lib/api.client.ts

import type { OrgUnitsTreeResponse } from "./types";

function getApiBase(): string {
  const v = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim().replace(/\/+$/, "");
  return v || "http://127.0.0.1:8000";
}

function getDevUserId(): string | null {
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v ? v : null;
}

function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null) return;
    const s = String(v).trim();
    if (!s) return;
    q.set(k, s);
  });
  return q.toString();
}

/**
 * Единая мапа ошибок fetch/HTTP → человеко-читаемый текст для UI.
 */
export function mapApiErrorToMessage(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e ?? "Unknown error");

  const m = msg.match(/\bHTTP\s+(\d{3})\b/i);
  const status = m ? Number(m[1]) : undefined;

  if (status === 401) return "Нет доступа (401).";
  if (status === 403) return "Недостаточно прав (403).";
  if (status === 404) return "Не найдено (404).";
  if (status && status >= 500) return "Ошибка сервера. Попробуйте позже.";
  return msg || "Ошибка запроса.";
}

async function apiGetJson<T>(path: string, qs?: string): Promise<T> {
  const apiBase = getApiBase();
  const devUserId = getDevUserId();

  const headers: Record<string, string> = { Accept: "application/json" };
  if (devUserId) headers["X-User-Id"] = devUserId;

  const url = qs ? `${apiBase}${path}?${qs}` : `${apiBase}${path}`;

  const res = await fetch(url, {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${t || res.statusText}`);
  }

  return (await res.json()) as T;
}

/**
 * UI-дерево оргструктуры
 * Backend: GET /directory/org-units/tree
 */
export async function getOrgUnitsTree(args?: {
  status?: "all" | "active";
  include_inactive?: boolean; // legacy
}): Promise<OrgUnitsTreeResponse> {
  const qs = buildQuery({
    status: args?.status ?? "all",
    include_inactive: args?.include_inactive,
  });
  return apiGetJson<OrgUnitsTreeResponse>("/directory/org-units/tree", qs);
}

async function apiPatchJson<T>(path: string, body: unknown): Promise<T> {
  const apiBase = getApiBase();
  const devUserId = getDevUserId();

  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  if (devUserId) headers["X-User-Id"] = devUserId;

  const res = await fetch(`${apiBase}${path}`, {
    method: "PATCH",
    headers,
    body: JSON.stringify(body),
    cache: "no-store",
  });

  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${t || res.statusText}`);
  }

  return (await res.json()) as T;
}

/**
 * Rename org unit
 * Backend: PATCH /directory/org-units/{unit_id}
 */
export async function renameOrgUnit(args: { unit_id: string | number; name: string }): Promise<{ ok: true }> {
  return apiPatchJson<{ ok: true }>(`/directory/org-units/${args.unit_id}`, { name: args.name });
}
