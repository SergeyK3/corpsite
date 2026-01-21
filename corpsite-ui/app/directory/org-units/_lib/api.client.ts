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
 * Важно: backend возвращает detail как строку или объект; мы вытаскиваем detail когда можем.
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

async function readErrorText(res: Response): Promise<string> {
  const ct = (res.headers.get("content-type") || "").toLowerCase();
  try {
    if (ct.includes("application/json")) {
      const j: any = await res.json();
      const detail = j?.detail ?? j?.message ?? j?.error;
      if (typeof detail === "string" && detail.trim()) return detail.trim();
      if (detail != null) return JSON.stringify(detail);
      return JSON.stringify(j);
    }
  } catch {
    // ignore
  }
  try {
    const t = await res.text();
    return (t || "").trim();
  } catch {
    return "";
  }
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
    const detail = await readErrorText(res);
    throw new Error(`HTTP ${res.status}: ${detail || res.statusText}`);
  }

  return (await res.json()) as T;
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
    const detail = await readErrorText(res);
    throw new Error(`HTTP ${res.status}: ${detail || res.statusText}`);
  }

  return (await res.json()) as T;
}

/**
 * UI-дерево оргструктуры
 * Backend: GET /directory/org-units/tree
 *
 * Важно: НЕ передаем одновременно status и include_inactive, чтобы избежать
 * неоднозначности (status у вас уже маппится в include_inactive на backend).
 */
export async function getOrgUnitsTree(args?: {
  status?: "all" | "active";
  include_inactive?: boolean; // legacy
}): Promise<OrgUnitsTreeResponse> {
  const hasLegacy = args?.include_inactive !== undefined && args?.include_inactive !== null;

  const qs = buildQuery(hasLegacy ? { include_inactive: args?.include_inactive } : { status: args?.status ?? "all" });

  return apiGetJson<OrgUnitsTreeResponse>("/directory/org-units/tree", qs);
}

/**
 * Общий формат item, который возвращает backend для rename/move.
 * (Сейчас он не совпадает с TreeNode, поэтому UI после операции делает reload tree.)
 */
export type OrgUnitMutationItem = {
  id: number;
  parent_id: number | null;
  name: string;
  code: string | null;
  is_active: boolean;
};

export type OrgUnitMutationResponse = {
  item: OrgUnitMutationItem;
};

/**
 * Rename org unit
 * Backend:
 * - основной: PATCH /directory/org-units/{unit_id}/rename
 * - совместимость: PATCH /directory/org-units/{unit_id}
 */
export async function renameOrgUnit(args: {
  unit_id: string | number;
  name: string;
}): Promise<OrgUnitMutationResponse> {
  const id = String(args.unit_id);
  const payload = { name: args.name };

  try {
    return await apiPatchJson<OrgUnitMutationResponse>(`/directory/org-units/${id}/rename`, payload);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e ?? "");
    if (/\bHTTP\s+404\b/i.test(msg)) {
      return apiPatchJson<OrgUnitMutationResponse>(`/directory/org-units/${id}`, payload);
    }
    throw e;
  }
}

/**
 * Move org unit
 * Backend: PATCH /directory/org-units/{unit_id}/move  body: { parent_unit_id: number | null }
 */
export async function moveOrgUnit(args: {
  unit_id: string | number;
  parent_unit_id: number | null;
}): Promise<OrgUnitMutationResponse> {
  const id = String(args.unit_id);
  const payload = { parent_unit_id: args.parent_unit_id };

  return apiPatchJson<OrgUnitMutationResponse>(`/directory/org-units/${id}/move`, payload);
}
