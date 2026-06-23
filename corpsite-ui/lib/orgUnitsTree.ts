// FILE: corpsite-ui/lib/orgUnitsTree.ts

import type { TreeNode } from "@/app/directory/org-units/_lib/api.client";

export type OrgUnitOption = {
  id: number;
  label: string;
};

/** Minimal node shape for sidebar/tree expansion helpers. */
export type OrgTreeNodeLike = {
  key: string;
  unit_id?: number | null;
  children?: OrgTreeNodeLike[];
};

export function flattenOrgUnits(nodes: TreeNode[], depth = 0): OrgUnitOption[] {
  const out: OrgUnitOption[] = [];

  for (const node of nodes) {
    const unitId = Number(node.unit_id ?? node.id);
    if (Number.isFinite(unitId) && unitId > 0) {
      const name = String(node.name ?? node.name_ru ?? `#${unitId}`).trim();
      out.push({ id: unitId, label: `${"— ".repeat(depth)}${name}` });
    }

    if (Array.isArray(node.children) && node.children.length > 0) {
      out.push(...flattenOrgUnits(node.children, depth + 1));
    }
  }

  return out;
}

/** Keys of ancestors that must be expanded so `unitId` is visible. */
export function collectAncestorKeysForUnitId(
  nodes: OrgTreeNodeLike[],
  unitId: number,
): Set<string> {
  const found = new Set<string>();

  function walk(node: OrgTreeNodeLike, ancestors: string[]): boolean {
    if (node.unit_id === unitId) {
      for (const key of ancestors) found.add(key);
      return true;
    }

    for (const child of node.children ?? []) {
      if (walk(child, [...ancestors, node.key])) return true;
    }

    return false;
  }

  for (const node of nodes) {
    walk(node, []);
  }

  return found;
}

/** All node keys that have children (for expanding search results). */
export function collectExpandableKeys(nodes: OrgTreeNodeLike[]): string[] {
  const keys: string[] = [];

  for (const node of nodes) {
    const children = node.children ?? [];
    if (children.length > 0) {
      keys.push(node.key);
      keys.push(...collectExpandableKeys(children));
    }
  }

  return keys;
}

/** Default sidebar expansion: collapsed groups; expand path to selection only. */
export function buildDefaultExpandedKeys(
  nodes: OrgTreeNodeLike[],
  selectedUnitId?: number | null,
): Set<string> {
  if (selectedUnitId == null || !Number.isFinite(selectedUnitId)) {
    return new Set();
  }

  return collectAncestorKeysForUnitId(nodes, Math.trunc(selectedUnitId));
}
