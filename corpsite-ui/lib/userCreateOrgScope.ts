import type { TreeNode } from "@/app/directory/org-units/_lib/api.client";
import { getOrgUnitsTree } from "@/app/directory/org-units/_lib/api.client";

export type EmployeeOrgScopePrefill = {
  org_group_id: number | null;
  org_unit_id: number | null;
};

/** Resolve department group for an org unit from org-units tree nodes. */
export function findOrgGroupIdForUnit(nodes: TreeNode[], unitId: number): number | null {
  const targetUnitId = Math.trunc(unitId);
  if (!Number.isFinite(targetUnitId) || targetUnitId <= 0) return null;

  function walk(node: TreeNode): number | null {
    const nodeUnitId = Number(node.unit_id ?? node.id);
    if (Number.isFinite(nodeUnitId) && nodeUnitId === targetUnitId) {
      const groupId = Number(node.group_id ?? 0);
      return Number.isFinite(groupId) && groupId > 0 ? groupId : null;
    }

    for (const child of node.children ?? []) {
      const found = walk(child);
      if (found != null) return found;
    }

    return null;
  }

  for (const node of nodes) {
    const found = walk(node);
    if (found != null) return found;
  }

  return null;
}

export function employeeOrgUnitId(details: Record<string, unknown> | null | undefined): number | null {
  if (!details) return null;

  const fromOrgUnit = Number(
    (details as { org_unit?: { unit_id?: unknown } }).org_unit?.unit_id ??
      (details as { orgUnit?: { unit_id?: unknown } }).orgUnit?.unit_id ??
      0,
  );
  if (Number.isFinite(fromOrgUnit) && fromOrgUnit > 0) return Math.trunc(fromOrgUnit);

  const topLevel = Number(
    (details as { org_unit_id?: unknown }).org_unit_id ?? (details as { unit_id?: unknown }).unit_id ?? 0,
  );
  if (Number.isFinite(topLevel) && topLevel > 0) return Math.trunc(topLevel);

  return null;
}

/** Prefill org scope for Platform User create form from employee operational unit. */
export async function resolveEmployeeOrgScopePrefill(
  unitId: number | null | undefined,
): Promise<EmployeeOrgScopePrefill> {
  const org_unit_id =
    unitId != null && Number.isFinite(unitId) && unitId > 0 ? Math.trunc(unitId) : null;
  if (org_unit_id == null) {
    return { org_group_id: null, org_unit_id: null };
  }

  const tree = await getOrgUnitsTree({});
  const org_group_id = findOrgGroupIdForUnit(tree.items ?? [], org_unit_id);
  return { org_group_id, org_unit_id };
}
