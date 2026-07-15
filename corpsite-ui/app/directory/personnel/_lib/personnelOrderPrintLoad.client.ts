import { getPositions } from "@/app/directory/employees/_lib/api.client";
import { getOrgUnitsTree, type TreeNode } from "@/app/directory/org-units/_lib/api.client";

import {
  getPersonnelOrder,
  getPersonnelOrderEditorial,
  type PersonnelOrderDetailResponse,
  type PersonnelOrderEditorialState,
} from "./personnelOrdersApi.client";
import {
  buildPersonnelOrderPrintViewModel,
  collectPersonnelOrderPrintLookupIds,
  type PersonnelOrderPrintNameMaps,
  type PersonnelOrderPrintViewModel,
} from "./personnelOrderPrintViewModel";

export type PersonnelOrderPrintLoadResult = {
  detail: PersonnelOrderDetailResponse;
  model: PersonnelOrderPrintViewModel;
  maps: PersonnelOrderPrintNameMaps;
};

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
    const res = await fetch("/tenant.json", { cache: "no-store" });
    if (!res.ok) return null;
    const json = (await res.json()) as { orgName?: string };
    const name = String(json?.orgName ?? "").trim();
    return name || null;
  } catch {
    return null;
  }
}

function buildPositionNames(
  positionsRaw: unknown,
  positionIds: number[],
): Record<number, string> {
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
    if (positionIds.length > 0 && !positionIds.includes(id)) continue;
    const name = String((row as { name?: string }).name ?? "").trim();
    if (name) positionNames[id] = name;
  }
  return positionNames;
}

/** Build print name maps from already loaded detail (shared by preview page and tests). */
export async function buildPersonnelOrderPrintNameMaps(
  detail: PersonnelOrderDetailResponse,
  editorial?: PersonnelOrderEditorialState | null,
): Promise<PersonnelOrderPrintNameMaps> {
  const ids = collectPersonnelOrderPrintLookupIds(detail);
  const [organizationName, tree, positionsRaw] = await Promise.all([
    loadOrganizationName(),
    getOrgUnitsTree({ include_inactive: false }).catch(() => null),
    getPositions({ limit: 1000, offset: 0 }).catch(() => null),
  ]);

  const orgUnitNames: Record<number, string> = {};
  if (tree?.items) flattenOrgUnitNames(tree.items, orgUnitNames);

  return {
    organizationName,
    orgUnitNames,
    positionNames: buildPositionNames(positionsRaw, ids.positionIds),
    editorial: editorial ?? null,
  };
}

/**
 * Same data path as the «Предпросмотр/Печать» button: GET order detail → directory lookups
 * → editorial → buildPersonnelOrderPrintViewModel.
 */
export async function loadPersonnelOrderPrintViewModelClient(
  orderId: number,
): Promise<PersonnelOrderPrintLoadResult> {
  const detail = await getPersonnelOrder(orderId);
  const editorial = await getPersonnelOrderEditorial(orderId).catch(() => null);
  const maps = await buildPersonnelOrderPrintNameMaps(detail, editorial);
  const model = buildPersonnelOrderPrintViewModel(detail, maps);
  return { detail, model, maps };
}
