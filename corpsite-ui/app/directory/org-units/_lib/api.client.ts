// FILE: corpsite-ui/app/directory/org-units/_lib/api.client.ts
"use client";

import type { OrgUnitsTreeResponse, OrgUnitTreeNode } from "./types";
import { apiFetchJson } from "../../../lib/api";

/**
 * apiFetchJson уже добавляет Authorization (Bearer) из sessionStorage,
 * поэтому здесь НЕЛЬЗЯ делать raw fetch без заголовков.
 */

function buildQuery(params: Record<string, string | number | boolean | null | undefined>): Record<string, any> {
  const out: Record<string, any> = {};
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null) continue;
    const s = String(v).trim();
    if (!s) continue;
    out[k] = typeof v === "boolean" ? (v ? 1 : 0) : v;
  }
  return out;
}

function toStringId(v: unknown): string {
  if (v === null || v === undefined) return "";
  return String(v);
}

// ---------------------------
// Error mapping
// ---------------------------

function extractStatus(e: any): number | undefined {
  const s =
    (typeof e?.status === "number" && e.status) ||
    (typeof e?.details?.status === "number" && e.details.status) ||
    (typeof e?.details?.status_code === "number" && e.details.status_code);

  if (typeof s === "number" && Number.isFinite(s)) return s;

  const msg = typeof e?.message === "string" ? e.message : "";
  const m = msg.match(/\bHTTP\s+(\d{3})\b/i);
  if (m) {
    const n = Number(m[1]);
    if (Number.isFinite(n)) return n;
  }
  return undefined;
}

export function mapApiErrorToMessage(e: unknown): string {
  const anyErr: any = e as any;
  const status = extractStatus(anyErr);

  if (status === 401) return "Нет доступа (401).";
  if (status === 403) return "Недостаточно прав (403).";
  if (status === 404) return "Не найдено (404).";
  if (status && status >= 500) return "Ошибка сервера. Попробуйте позже.";

  // prefer APIError.message
  const msg =
    (typeof anyErr?.message === "string" && anyErr.message.trim()) ||
    (typeof anyErr?.detail === "string" && anyErr.detail.trim()) ||
    "";

  return msg || "Ошибка запроса.";
}

// ---------------------------
// Tree normalization (UI expects string ids)
// ---------------------------

function normalizeTreeNode(node: any): OrgUnitTreeNode {
  const childrenRaw = Array.isArray(node?.children) ? node.children : [];
  return {
    ...node,
    id: toStringId(node?.id),
    children: childrenRaw.map(normalizeTreeNode),
  } as OrgUnitTreeNode;
}

function normalizeTreeResponse(raw: any): OrgUnitsTreeResponse {
  const itemsRaw = Array.isArray(raw?.items) ? raw.items : [];
  const inactiveRaw = Array.isArray(raw?.inactive_ids) ? raw.inactive_ids : [];

  return {
    ...raw,
    items: itemsRaw.map(normalizeTreeNode),
    inactive_ids: inactiveRaw.map((x: any) => toStringId(x)).filter((s: string) => s !== ""),
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

  const query = hasLegacy
    ? buildQuery({ include_inactive: args?.include_inactive })
    : buildQuery({ status: args?.status ?? "all" });

  const raw = await apiFetchJson<any>("/directory/org-units/tree", { query });
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

export async function renameOrgUnit(args: { unit_id: string | number; name: string }): Promise<OrgUnitMutationResponse> {
  const id = String(args.unit_id);
  const payload = { name: args.name };

  try {
    // preferred
    return await apiFetchJson<OrgUnitMutationResponse>(`/directory/org-units/${id}/rename`, {
      method: "PATCH",
      body: payload,
    });
  } catch (e: any) {
    const status = extractStatus(e);
    if (status === 404) {
      // fallback (older contract)
      return await apiFetchJson<OrgUnitMutationResponse>(`/directory/org-units/${id}`, {
        method: "PATCH",
        body: payload,
      });
    }
    throw e;
  }
}

export async function moveOrgUnit(args: {
  unit_id: string | number;
  parent_unit_id: number | null;
}): Promise<OrgUnitMutationResponse> {
  const id = String(args.unit_id);
  return await apiFetchJson<OrgUnitMutationResponse>(`/directory/org-units/${id}/move`, {
    method: "PATCH",
    body: { parent_unit_id: args.parent_unit_id },
  });
}

export async function deactivateOrgUnit(args: { unit_id: string | number }): Promise<OrgUnitMutationResponse> {
  const id = String(args.unit_id);
  return await apiFetchJson<OrgUnitMutationResponse>(`/directory/org-units/${id}/deactivate`, {
    method: "PATCH",
    body: {},
  });
}

export async function activateOrgUnit(args: { unit_id: string | number }): Promise<OrgUnitMutationResponse> {
  const id = String(args.unit_id);
  return await apiFetchJson<OrgUnitMutationResponse>(`/directory/org-units/${id}/activate`, {
    method: "PATCH",
    body: {},
  });
}

export async function createOrgUnit(args: {
  name: string;
  parent_unit_id?: number | null;
  code?: string | null;
  is_active?: boolean;
}): Promise<OrgUnitMutationResponse> {
  return await apiFetchJson<OrgUnitMutationResponse>(`/directory/org-units`, {
    method: "POST",
    body: {
      name: args.name,
      parent_unit_id: args.parent_unit_id ?? null,
      code: args.code ?? null,
      is_active: args.is_active ?? true,
    },
  });
}
