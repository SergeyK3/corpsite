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
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    const s = String(v).trim();
    if (!s) continue;
    q.set(k, s);
  }
  return q.toString();
}

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

// ---------------------------
// Tree normalization (fix TS: TreeNode.id must be string)
// ---------------------------

function toStringId(v: unknown): string {
  if (v === null || v === undefined) return "";
  return String(v);
}

function normalizeTreeNode(node: any): OrgUnitTreeNode {
  const childrenRaw = Array.isArray(node?.children) ? node.children : [];
  return {
    ...node,
    id: toStringId(node?.id),
    // (optional) если parent_id/parent_unit_id в node нужен как number|null — не трогаем.
    children: childrenRaw.map(normalizeTreeNode),
  } as OrgUnitTreeNode;
}

function normalizeTreeResponse(raw: any): OrgUnitsTreeResponse {
  const itemsRaw = Array.isArray(raw?.items) ? raw.items : [];
  const inactiveRaw = Array.isArray(raw?.inactive_ids) ? raw.inactive_ids : [];

  return {
    ...raw,
    // items: всегда массив, и каждый id приведён к string
    items: itemsRaw.map(normalizeTreeNode),
    // inactive_ids: приведём к string[], чтобы не конфликтовало с UI (обычно UI хранит id как string)
    inactive_ids: inactiveRaw.map((x: any) => toStringId(x)).filter((s: string) => s !== ""),
    // root_id: тоже в string (если в types ожидается number — скажете, но тогда нужно будет синхронизировать UI)
    root_id: raw?.root_id === null || raw?.root_id === undefined ? null : toStringId(raw.root_id),
  } as OrgUnitsTreeResponse;
}

/**
 * UI-дерево оргструктуры
 * Backend: GET /directory/org-units/tree
 */
export async function getOrgUnitsTree(args?: {
  status?: "all" | "active";
  include_inactive?: boolean; // legacy
}): Promise<OrgUnitsTreeResponse> {
  const hasLegacy = args?.include_inactive !== undefined && args?.include_inactive !== null;

  const qs = buildQuery(
    hasLegacy ? { include_inactive: args?.include_inactive } : { status: args?.status ?? "all" }
  );

  const raw = await apiGetJson<any>("/directory/org-units/tree", qs);
  return normalizeTreeResponse(raw);
}

/**
 * Общий формат item, который возвращает backend для rename/move/activate/deactivate/create.
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

export async function moveOrgUnit(args: {
  unit_id: string | number;
  parent_unit_id: number | null;
}): Promise<OrgUnitMutationResponse> {
  const id = String(args.unit_id);
  const payload = { parent_unit_id: args.parent_unit_id };

  return apiPatchJson<OrgUnitMutationResponse>(`/directory/org-units/${id}/move`, payload);
}

export async function deactivateOrgUnit(args: {
  unit_id: string | number;
}): Promise<OrgUnitMutationResponse> {
  const id = String(args.unit_id);
  return apiPatchJson<OrgUnitMutationResponse>(`/directory/org-units/${id}/deactivate`, {});
}

export async function activateOrgUnit(args: {
  unit_id: string | number;
}): Promise<OrgUnitMutationResponse> {
  const id = String(args.unit_id);
  return apiPatchJson<OrgUnitMutationResponse>(`/directory/org-units/${id}/activate`, {});
}

export async function createOrgUnit(args: {
  name: string;
  parent_unit_id?: number | null;
  code?: string | null;
  is_active?: boolean;
}): Promise<OrgUnitMutationResponse> {
  const payload = {
    name: args.name,
    parent_unit_id: args.parent_unit_id ?? null,
    code: args.code ?? null,
    is_active: args.is_active ?? true,
  };
  return apiPostJson<OrgUnitMutationResponse>(`/directory/org-units`, payload);
}
