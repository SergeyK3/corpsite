import { readFile } from "node:fs/promises";
import path from "node:path";

import { resolveApiUrl } from "@/lib/apiBase";

import type { PersonnelOrderDetailResponse } from "./personnelOrdersApi.client";
import {
  buildPersonnelOrderPrintViewModel,
  collectPersonnelOrderPrintLookupIds,
  type PersonnelOrderPrintViewModel,
} from "./personnelOrderPrintViewModel";
import type { PersonnelOrderPdfAuthContext } from "./personnelOrderPdfAuth";

export class PersonnelOrderPdfDataError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "PersonnelOrderPdfDataError";
    this.status = status;
    this.code = code;
  }
}

type TreeNode = {
  id?: number;
  unit_id?: number;
  name?: string;
  name_ru?: string;
  children?: TreeNode[];
};

function authHeaders(auth: PersonnelOrderPdfAuthContext): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (auth.authorizationHeader) headers.Authorization = auth.authorizationHeader;
  if (auth.devUserId) headers["X-User-Id"] = auth.devUserId;
  return headers;
}

async function fetchJson<T>(
  pathName: string,
  auth: PersonnelOrderPdfAuthContext,
  fallback: string,
): Promise<T> {
  const res = await fetch(resolveApiUrl(pathName, { serverSide: true }), {
    method: "GET",
    headers: authHeaders(auth),
    cache: "no-store",
  });
  if (!res.ok) {
    if (res.status === 401) {
      throw new PersonnelOrderPdfDataError(401, "UNAUTHORIZED", "Требуется авторизация.");
    }
    if (res.status === 403) {
      throw new PersonnelOrderPdfDataError(
        403,
        "FORBIDDEN",
        "Недостаточно прав для работы с кадровыми приказами.",
      );
    }
    if (res.status === 404) {
      throw new PersonnelOrderPdfDataError(404, "NOT_FOUND", "Приказ не найден.");
    }
    throw new PersonnelOrderPdfDataError(res.status, "UPSTREAM_ERROR", fallback);
  }
  return res.json() as Promise<T>;
}

function flattenOrgUnitNames(nodes: TreeNode[], out: Record<number, string>) {
  for (const node of nodes) {
    const unitId = Number(node.unit_id ?? node.id);
    if (Number.isFinite(unitId) && unitId > 0) {
      const name = String(node.name ?? node.name_ru ?? "").trim();
      if (name) out[unitId] = name;
    }
    if (Array.isArray(node.children) && node.children.length > 0) {
      flattenOrgUnitNames(node.children, out);
    }
  }
}

async function loadOrganizationName(): Promise<string | null> {
  try {
    const filePath = path.join(process.cwd(), "public", "tenant.json");
    const raw = await readFile(filePath, "utf8");
    const json = JSON.parse(raw) as { orgName?: string };
    const name = String(json?.orgName ?? "").trim();
    return name || null;
  } catch {
    return null;
  }
}

/**
 * Load order detail + directory lookups and build the shared print ViewModel.
 * Same authorization as detail/print (caller Bearer / dev user forwarded to FastAPI).
 */
export async function loadPersonnelOrderPrintViewModelForPdf(
  orderId: number,
  auth: PersonnelOrderPdfAuthContext,
): Promise<PersonnelOrderPrintViewModel> {
  const detail = await fetchJson<PersonnelOrderDetailResponse>(
    `/directory/personnel-orders/${orderId}`,
    auth,
    "Не удалось загрузить приказ.",
  );

  const ids = collectPersonnelOrderPrintLookupIds(detail);
  const [organizationName, tree, positionsRaw] = await Promise.all([
    loadOrganizationName(),
    fetchJson<{ items?: TreeNode[] }>(
      "/directory/org-units/tree?include_inactive=false",
      auth,
      "Не удалось загрузить оргструктуру.",
    ).catch(() => null),
    fetchJson<unknown>(
      "/directory/positions?limit=1000&offset=0",
      auth,
      "Не удалось загрузить должности.",
    ).catch(() => null),
  ]);

  const orgUnitNames: Record<number, string> = {};
  if (tree?.items) flattenOrgUnitNames(tree.items, orgUnitNames);

  const positionNames: Record<number, string> = {};
  const list = Array.isArray(positionsRaw)
    ? positionsRaw
    : Array.isArray((positionsRaw as { items?: unknown[] } | null)?.items)
      ? ((positionsRaw as { items: unknown[] }).items)
      : [];
  for (const row of list) {
    const id = Number(
      (row as { position_id?: number; id?: number }).position_id ??
        (row as { id?: number }).id,
    );
    if (!Number.isFinite(id) || id <= 0) continue;
    if (ids.positionIds.length > 0 && !ids.positionIds.includes(id)) continue;
    const name = String((row as { name?: string }).name ?? "").trim();
    if (name) positionNames[id] = name;
  }

  return buildPersonnelOrderPrintViewModel(detail, {
    organizationName,
    orgUnitNames,
    positionNames,
  });
}
