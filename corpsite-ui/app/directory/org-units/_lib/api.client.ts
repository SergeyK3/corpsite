// FILE: corpsite-ui/app/directory/org-units/_lib/api.client.ts
"use client";

import { apiFetchJson } from "../../../../lib/api";

export type TreeNode = {
  id: string;
  unit_id?: number;
  code?: string | null;
  name: string;
  name_ru?: string | null;
  name_en?: string | null;
  parent_unit_id?: number | null;
  group_id?: number | null;
  is_active?: boolean;
  unit_type?: string | null;
  org_level?: number | null;
  sort_order1?: number | null;
  sort_order2?: number | null;
  children?: TreeNode[];
};

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
  if (status === 409) return "Конфликт данных (409).";
  if (status === 422) {
    const detail =
      (typeof anyErr?.detail === "string" && anyErr.detail.trim()) ||
      (typeof anyErr?.message === "string" && anyErr.message.trim()) ||
      "";
    return detail || "Некорректные данные (422).";
  }
  if (status && status >= 500) return "Ошибка сервера. Попробуйте позже.";

  const msg =
    (typeof anyErr?.message === "string" && anyErr.message.trim()) ||
    (typeof anyErr?.detail === "string" && anyErr.detail.trim()) ||
    "";

  return msg || "Ошибка запроса.";
}

function normalizeTreeNode(raw: any): TreeNode {
  const unitId = Number(raw?.unit_id ?? raw?.id ?? 0);

  return {
    id: String(raw?.id ?? raw?.unit_id ?? ""),
    unit_id: Number.isFinite(unitId) && unitId > 0 ? unitId : undefined,
    code: raw?.code ?? null,
    name:
      String(raw?.name_ru ?? "").trim() ||
      String(raw?.name ?? "").trim() ||
      String(raw?.title ?? "").trim() ||
      (Number.isFinite(unitId) && unitId > 0 ? `Unit #${unitId}` : "Подразделение"),
    name_ru: raw?.name_ru ?? null,
    name_en: raw?.name_en ?? null,
    parent_unit_id:
      raw?.parent_unit_id === null || raw?.parent_unit_id === undefined
        ? null
        : Number(raw.parent_unit_id),
    group_id:
      raw?.group_id === null || raw?.group_id === undefined
        ? null
        : Number(raw.group_id),
    is_active:
      typeof raw?.is_active === "boolean"
        ? raw.is_active
        : raw?.is_active === 1
          ? true
          : raw?.is_active === 0
            ? false
            : undefined,
    unit_type: raw?.unit_type ?? null,
    org_level:
      raw?.org_level === null || raw?.org_level === undefined
        ? null
        : Number(raw.org_level),
    sort_order1:
      raw?.sort_order1 === null || raw?.sort_order1 === undefined
        ? null
        : Number(raw.sort_order1),
    sort_order2:
      raw?.sort_order2 === null || raw?.sort_order2 === undefined
        ? null
        : Number(raw.sort_order2),
    children: Array.isArray(raw?.children) ? raw.children.map(normalizeTreeNode) : [],
  };
}

function normalizeTreeResponse(body: any): TreeNode[] {
  if (Array.isArray(body)) return body.map(normalizeTreeNode);
  if (Array.isArray(body?.items)) return body.items.map(normalizeTreeNode);
  if (Array.isArray(body?.nodes)) return body.nodes.map(normalizeTreeNode);
  if (Array.isArray(body?.tree)) return body.tree.map(normalizeTreeNode);
  return [];
}

/**
 * Дерево орг-юнитов.
 * Предпочтительный backend endpoint:
 *   GET /directory/org-units/tree
 * Фолбэк:
 *   GET /directory/org/tree
 */
export type OrgUnitsTreePayload = {
  items: TreeNode[];
  inactive_ids: string[];
  root_id: number | string | null;
};

export async function getOrgUnitsTree(args?: {
  include_inactive?: boolean;
}): Promise<OrgUnitsTreePayload> {
  const query = buildQuery({
    include_inactive: args?.include_inactive ?? undefined,
  });

  function pack(body: any): OrgUnitsTreePayload {
    const items = normalizeTreeResponse(body);
    const inactive_ids = Array.isArray(body?.inactive_ids)
      ? (body.inactive_ids as unknown[]).map((x) => String(x))
      : [];
    const root_id = body?.root_id ?? null;
    return { items, inactive_ids, root_id };
  }

  try {
    const body = await apiFetchJson<any>("/directory/org-units/tree", { query });
    return pack(body);
  } catch (e: any) {
    const status = extractStatus(e);
    if (status && status !== 404) throw e;

    const body = await apiFetchJson<any>("/directory/org/tree", { query });
    return pack(body);
  }
}

/**
 * Создание org-unit.
 * Предпочтительный endpoint:
 *   POST /directory/org-units
 */
export async function createOrgUnit(payload: {
  name?: string;
  name_ru?: string;
  name_en?: string;
  code?: string;
  parent_unit_id?: number | null;
  group_id?: number | null;
  unit_type?: string | null;
  org_level?: number | null;
  sort_order1?: number | null;
  sort_order2?: number | null;
  is_active?: boolean;
}): Promise<any> {
  return await apiFetchJson<any>("/directory/org-units", {
    method: "POST",
    body: payload,
  });
}

/**
 * Переименование / обновление полей org-unit.
 * Предпочтительный endpoint:
 *   PATCH /directory/org-units/{id}
 */
export async function renameOrgUnit(
  unitId: string | number,
  payload: {
    name?: string;
    name_ru?: string;
    name_en?: string;
    code?: string;
  },
): Promise<any> {
  const id = String(unitId).trim();
  if (!id) throw new Error("Unit id is empty");

  return await apiFetchJson<any>(`/directory/org-units/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: payload,
  });
}

/**
 * Перемещение org-unit.
 * Предпочтительный endpoint:
 *   POST /directory/org-units/{id}/move
 * Фолбэк:
 *   PATCH /directory/org-units/{id} с parent_unit_id
 */
export async function moveOrgUnit(
  unitId: string | number,
  payload: {
    parent_unit_id?: number | null;
    sort_order1?: number | null;
    sort_order2?: number | null;
  },
): Promise<any> {
  const id = String(unitId).trim();
  if (!id) throw new Error("Unit id is empty");

  try {
    return await apiFetchJson<any>(`/directory/org-units/${encodeURIComponent(id)}/move`, {
      method: "POST",
      body: payload,
    });
  } catch (e: any) {
    const status = extractStatus(e);
    if (status && status !== 404) throw e;

    return await apiFetchJson<any>(`/directory/org-units/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: payload,
    });
  }
}

/**
 * Активация org-unit.
 * Предпочтительный endpoint:
 *   POST /directory/org-units/{id}/activate
 * Фолбэк:
 *   PATCH /directory/org-units/{id} { is_active: true }
 */
export async function activateOrgUnit(unitId: string | number): Promise<any> {
  const id = String(unitId).trim();
  if (!id) throw new Error("Unit id is empty");

  try {
    return await apiFetchJson<any>(`/directory/org-units/${encodeURIComponent(id)}/activate`, {
      method: "POST",
    });
  } catch (e: any) {
    const status = extractStatus(e);
    if (status && status !== 404) throw e;

    return await apiFetchJson<any>(`/directory/org-units/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: { is_active: true },
    });
  }
}

/**
 * Деактивация org-unit.
 * Предпочтительный endpoint:
 *   POST /directory/org-units/{id}/deactivate
 * Фолбэк:
 *   PATCH /directory/org-units/{id} { is_active: false }
 */
export async function deactivateOrgUnit(unitId: string | number): Promise<any> {
  const id = String(unitId).trim();
  if (!id) throw new Error("Unit id is empty");

  try {
    return await apiFetchJson<any>(`/directory/org-units/${encodeURIComponent(id)}/deactivate`, {
      method: "POST",
    });
  } catch (e: any) {
    const status = extractStatus(e);
    if (status && status !== 404) throw e;

    return await apiFetchJson<any>(`/directory/org-units/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: { is_active: false },
    });
  }
}