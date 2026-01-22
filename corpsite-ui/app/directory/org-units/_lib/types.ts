// FILE: corpsite-ui/app/directory/org-units/_lib/api.client.ts

import type { OrgUnitsTreeResponse, OrgUnitTreeNode } from "./types";

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

async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  const apiBase = getApiBase();
  const devUserId = getDevUserId();

  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  if (devUserId) headers["X-User-Id"] = devUserId;

  const res = await fetch(`${apiBase}${path}`, {
    method: "POST",
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
 * Rename org unit
 * Backend:
 * - основной: PATCH /directory/org-units/{unit_id}/rename  (новый)
 * - совместимость: PATCH /directory/org-units/{unit_id}   (старый)
 *
 * Ответ backend сейчас: { item: { id, parent_id, name, code, is_active } }
 * UI-дерево оперирует полями { id, title, type, is_active }, поэтому тут
 * возвращаем "сырой" item как есть (без попытки угадать type/title).
 */
export type OrgUnitRenameResponse = {
  item: {
    id: string | number;
    parent_id: number | null;
    name: string;
    code: string | null;
    is_active: boolean;
  };
};

export async function renameOrgUnit(args: { unit_id: string | number; name: string }): Promise<OrgUnitRenameResponse> {
  const id = String(args.unit_id);
  const payload = { name: args.name };

  try {
    return await apiPatchJson<OrgUnitRenameResponse>(`/directory/org-units/${id}/rename`, payload);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e ?? "");
    if (/\bHTTP\s+404\b/i.test(msg)) {
      return apiPatchJson<OrgUnitRenameResponse>(`/directory/org-units/${id}`, payload);
    }
    throw e;
  }
}

/**
 * Move org unit
 * Backend: PATCH /directory/org-units/{unit_id}/move  body: { parent_unit_id: number | null }
 */
export type OrgUnitMoveResponse = OrgUnitRenameResponse;

export async function moveOrgUnit(args: {
  unit_id: string | number;
  parent_unit_id: number | null;
}): Promise<OrgUnitMoveResponse> {
  const id = String(args.unit_id);
  const payload = { parent_unit_id: args.parent_unit_id };
  return apiPatchJson<OrgUnitMoveResponse>(`/directory/org-units/${id}/move`, payload);
}

/**
 * B3.3 Deactivate org unit
 * Backend: PATCH /directory/org-units/{unit_id}/deactivate
 */
export type OrgUnitDeactivateResponse = OrgUnitRenameResponse;

export async function deactivateOrgUnit(args: { unit_id: string | number }): Promise<OrgUnitDeactivateResponse> {
  const id = String(args.unit_id);
  return apiPatchJson<OrgUnitDeactivateResponse>(`/directory/org-units/${id}/deactivate`, {});
}

/**
 * B3.3 Activate org unit
 * Backend: PATCH /directory/org-units/{unit_id}/activate
 */
export type OrgUnitActivateResponse = OrgUnitRenameResponse;

export async function activateOrgUnit(args: { unit_id: string | number }): Promise<OrgUnitActivateResponse> {
  const id = String(args.unit_id);
  return apiPatchJson<OrgUnitActivateResponse>(`/directory/org-units/${id}/activate`, {});
}

/**
 * B4 Create org unit
 * Backend: POST /directory/org-units
 */
export type OrgUnitCreateResponse = OrgUnitRenameResponse;

export async function createOrgUnit(args: {
  name: string;
  parent_unit_id?: number | null;
  code?: string | null;
  is_active?: boolean;
}): Promise<OrgUnitCreateResponse> {
  const payload = {
    name: args.name,
    parent_unit_id: args.parent_unit_id ?? null,
    code: args.code ?? null,
    is_active: args.is_active ?? true,
  };
  return apiPostJson<OrgUnitCreateResponse>(`/directory/org-units`, payload);
}
