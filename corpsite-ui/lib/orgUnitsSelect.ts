import { apiFetchJson } from "@/lib/api";
import { loadDepartmentGroupLabelMap } from "@/lib/orgScope";

export type OrgUnitSelectOption = {
  unit_id: number;
  name: string;
  group_id: number | null;
};

type OrgUnitRow = {
  id?: number | string;
  unit_id?: number;
  unitId?: number;
  parent_id?: number | string | null;
  parent_unit_id?: number | null;
  parentId?: number | null;
  parentUnitId?: number | null;
  name?: string | null;
  title?: string | null;
  code?: string | null;
  group_id?: number | string | null;
  groupId?: number | string | null;
  children?: OrgUnitRow[];
};

type OrgTreeNode = {
  key: string;
  unit_id: number | null;
  name: string;
  group_id: number | null;
  children: OrgTreeNode[];
};

type OrgUnitsListResponse = {
  items?: OrgUnitRow[];
};

const HIDDEN_VISIBLE_ROOT_NAME = "Многопрофильный медицинский центр";

function normalizeText(v: unknown): string {
  return String(v ?? "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/[ё]/g, "е")
    .trim();
}

function unitIdOf(row: OrgUnitRow): number | null {
  const direct = row.unit_id ?? row.unitId;
  if (typeof direct === "number" && Number.isFinite(direct) && direct > 0) return direct;
  const parsed = Number(row.id);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function unitNameOf(row: OrgUnitRow): string {
  const name = String(row.title ?? row.name ?? row.code ?? "").trim();
  const id = unitIdOf(row);
  return name || (id != null ? `#${id}` : "—");
}

function ownGroupId(row: OrgUnitRow | OrgTreeNode): number | null {
  const g = row.group_id ?? (row as OrgUnitRow).groupId;
  if (typeof g === "number" && Number.isFinite(g) && g > 0) return Math.trunc(g);
  if (typeof g === "string" && g.trim()) {
    const parsed = Number(g.trim());
    if (Number.isFinite(parsed) && parsed > 0) return Math.trunc(parsed);
  }
  return null;
}

function dedupeOrgUnitOptions(items: OrgUnitSelectOption[]): OrgUnitSelectOption[] {
  const byUnitId = new Map<number, OrgUnitSelectOption>();

  for (const item of items) {
    const existing = byUnitId.get(item.unit_id);
    if (!existing) {
      byUnitId.set(item.unit_id, item);
      continue;
    }
    if (existing.group_id == null && item.group_id != null) {
      byUnitId.set(item.unit_id, item);
    }
  }

  return Array.from(byUnitId.values()).sort((a, b) => a.name.localeCompare(b.name, "ru"));
}

function nodeKey(raw: OrgUnitRow): string {
  const v = raw.id ?? raw.code ?? raw.unit_id ?? raw.unitId;
  return String(v ?? "").trim() || "unknown";
}

function normalizeOrgUnitNodeTree(raw: OrgUnitRow): OrgTreeNode {
  const childrenRaw = Array.isArray(raw.children) ? raw.children : [];
  return {
    key: nodeKey(raw),
    unit_id: unitIdOf(raw),
    name: unitNameOf(raw),
    group_id: ownGroupId(raw),
    children: childrenRaw.map(normalizeOrgUnitNodeTree),
  };
}

function buildTreeFromFlat(itemsRaw: OrgUnitRow[]): OrgTreeNode[] {
  const nodes = itemsRaw.map((x) => ({
    raw: x,
    key: nodeKey(x),
    unit_id: unitIdOf(x),
    name: unitNameOf(x),
    group_id: ownGroupId(x),
  }));

  const byKey = new Map<string, OrgTreeNode>();
  nodes.forEach((n) =>
    byKey.set(n.key, {
      key: n.key,
      unit_id: n.unit_id,
      name: n.name,
      group_id: n.group_id,
      children: [],
    }),
  );

  const parentOf = (x: OrgUnitRow): string | null => {
    const p = x.parentId ?? x.parent_id ?? x.parent_unit_id ?? x.parentUnitId;
    if (p === null || p === undefined) return null;
    return String(p).trim() || null;
  };

  const roots: OrgTreeNode[] = [];
  nodes.forEach((n) => {
    const pKey = parentOf(n.raw);
    const cur = byKey.get(n.key)!;
    if (pKey && byKey.has(pKey)) byKey.get(pKey)!.children.push(cur);
    else roots.push(cur);
  });

  return roots;
}

function groupChildrenByGroupId(
  children: OrgTreeNode[],
  groupLabelById: Map<number, string>,
  parentGroupId: number | null = null,
): OrgTreeNode[] {
  const buckets = new Map<number, OrgTreeNode[]>();
  const rest: OrgTreeNode[] = [];

  for (const ch of children) {
    const gid = ownGroupId(ch) ?? parentGroupId;
    if (gid != null && groupLabelById.has(gid)) {
      if (!buckets.has(gid)) buckets.set(gid, []);
      buckets.get(gid)!.push(ch);
    } else {
      rest.push(ch);
    }
  }

  const grouped: OrgTreeNode[] = Array.from(buckets.keys())
    .sort((a, b) => a - b)
    .map((gid) => ({
      key: `group-${gid}`,
      unit_id: null,
      name: groupLabelById.get(gid) ?? `Группа ${gid}`,
      group_id: gid,
      children: (buckets.get(gid) ?? []).sort((a, b) =>
        normalizeText(a.name).localeCompare(normalizeText(b.name), "ru"),
      ),
    }));

  const restSorted = rest.sort((a, b) => normalizeText(a.name).localeCompare(normalizeText(b.name), "ru"));
  return [...grouped, ...restSorted];
}

function injectGroupsIfPossible(tree: OrgTreeNode[], groupLabelById: Map<number, string>): OrgTreeNode[] {
  if (!Array.isArray(tree) || tree.length === 0) return tree;

  if (tree.length === 1 && Array.isArray(tree[0].children) && tree[0].children.length > 0) {
    const root = tree[0];
    const rootGroupId = ownGroupId(root);
    const hasGroupIds =
      (rootGroupId != null && groupLabelById.has(rootGroupId)) ||
      root.children.some((c) => {
        const gid = ownGroupId(c) ?? rootGroupId;
        return gid != null && groupLabelById.has(gid);
      });
    const alreadyGrouped = root.children.some((c) => c.key.startsWith("group-"));

    if (hasGroupIds && !alreadyGrouped) {
      return [{ ...root, children: groupChildrenByGroupId(root.children, groupLabelById, rootGroupId) }];
    }
  }

  return tree;
}

type PreparedOrgTree = {
  nodes: OrgTreeNode[];
  inheritedGroupId: number | null;
};

function stripVisibleRootIfNeeded(
  tree: OrgTreeNode[],
  inheritedGroupId: number | null = null,
): PreparedOrgTree {
  if (!Array.isArray(tree) || tree.length !== 1) {
    return { nodes: tree, inheritedGroupId };
  }

  const root = tree[0];
  const hasChildren = Array.isArray(root.children) && root.children.length > 0;
  if (!hasChildren) return { nodes: tree, inheritedGroupId };

  if (normalizeText(root.name) === normalizeText(HIDDEN_VISIBLE_ROOT_NAME)) {
    const rootGroup = ownGroupId(root) ?? inheritedGroupId;
    return { nodes: root.children, inheritedGroupId: rootGroup };
  }

  return { nodes: tree, inheritedGroupId };
}

function prepareOrgTree(itemsRaw: OrgUnitRow[], groupLabelById: Map<number, string>): PreparedOrgTree {
  const looksTree = itemsRaw.some((x) => Array.isArray(x.children) && (x.children?.length ?? 0) > 0);
  let tree: OrgTreeNode[];
  if (looksTree) {
    tree = itemsRaw.map(normalizeOrgUnitNodeTree);
  } else {
    const flatHasParents = itemsRaw.some(
      (x) => x.parentId != null || x.parent_id != null || x.parent_unit_id != null || x.parentUnitId != null,
    );
    tree = flatHasParents ? buildTreeFromFlat(itemsRaw) : itemsRaw.map(normalizeOrgUnitNodeTree);
  }

  const grouped = injectGroupsIfPossible(tree, groupLabelById);
  return stripVisibleRootIfNeeded(grouped);
}

function flattenOrgUnitTree(nodes: OrgTreeNode[], inheritedGroupId: number | null = null): OrgUnitSelectOption[] {
  const out: OrgUnitSelectOption[] = [];

  const walk = (list: OrgTreeNode[], parentGroupId: number | null) => {
    for (const node of list) {
      const effectiveGroup = ownGroupId(node) ?? parentGroupId;
      if (node.unit_id != null && node.unit_id > 0) {
        out.push({
          unit_id: node.unit_id,
          name: node.name,
          group_id: effectiveGroup,
        });
      }
      if (node.children.length > 0) {
        walk(node.children, effectiveGroup);
      }
    }
  };

  walk(nodes, inheritedGroupId);
  return dedupeOrgUnitOptions(out);
}

function enrichFlatOrgUnitsWithInheritedGroup(rows: OrgUnitRow[]): OrgUnitSelectOption[] {
  const byId = new Map<number, OrgUnitRow>();
  for (const row of rows) {
    const id = unitIdOf(row);
    if (id != null) byId.set(id, row);
  }

  const resolveGroup = (id: number, seen = new Set<number>()): number | null => {
    if (seen.has(id)) return null;
    seen.add(id);
    const row = byId.get(id);
    if (!row) return null;
    const own = ownGroupId(row);
    if (own != null) return own;
    const parentRaw = row.parent_unit_id ?? row.parent_id ?? row.parentId ?? row.parentUnitId;
    const parentId = Number(parentRaw);
    if (Number.isFinite(parentId) && parentId > 0) return resolveGroup(parentId, seen);
    return null;
  };

  return dedupeOrgUnitOptions(
    rows.flatMap((row): OrgUnitSelectOption[] => {
      const unitId = unitIdOf(row);
      if (unitId == null) return [];
      return [
        {
          unit_id: unitId,
          name: unitNameOf(row),
          group_id: resolveGroup(unitId),
        },
      ];
    }),
  );
}

function mergeOrgUnitOptions(...lists: OrgUnitSelectOption[][]): OrgUnitSelectOption[] {
  return dedupeOrgUnitOptions(lists.flat());
}

/** Build select options from API payloads (tree + flat). Exported for tests and cascade pipelines. */
export function buildOrgUnitSelectOptionsFromRows(
  treeRows: OrgUnitRow[],
  flatRows: OrgUnitRow[],
  groupLabelById: Map<number, string>,
): OrgUnitSelectOption[] {
  const collected: OrgUnitSelectOption[][] = [];

  if (treeRows.length > 0) {
    const prepared = prepareOrgTree(treeRows, groupLabelById);
    collected.push(flattenOrgUnitTree(prepared.nodes, prepared.inheritedGroupId));
  }

  if (flatRows.length > 0) {
    collected.push(enrichFlatOrgUnitsWithInheritedGroup(flatRows));
  }

  return mergeOrgUnitOptions(...collected);
}

export async function loadOrgUnitSelectOptions(): Promise<OrgUnitSelectOption[]> {
  const groupLabelById = await loadDepartmentGroupLabelMap();
  const collected: OrgUnitSelectOption[][] = [];

  try {
    const tree = await apiFetchJson<{ items?: OrgUnitRow[] }>("/directory/org-units/tree", {
      query: { status: "active" },
    });
    const itemsRaw = Array.isArray(tree?.items) ? tree.items : [];
    if (itemsRaw.length > 0) {
      const prepared = prepareOrgTree(itemsRaw, groupLabelById);
      collected.push(flattenOrgUnitTree(prepared.nodes, prepared.inheritedGroupId));
    }
  } catch {
    // try flat fallback below
  }

  try {
    const flat = await apiFetchJson<OrgUnitsListResponse>("/directory/org-units", {
      query: { status: "active" },
    });
    const rows = Array.isArray(flat?.items) ? flat.items : [];
    if (rows.length > 0) {
      collected.push(enrichFlatOrgUnitsWithInheritedGroup(rows));
    }
  } catch {
    // ignore, merged result may still be non-empty
  }

  const merged = mergeOrgUnitOptions(...collected);
  if (merged.length === 0) {
    throw new Error("Справочник отделений вернул пустой список. Проверьте /directory/org-units и права admin.");
  }

  return merged;
}

export type OrgUnitSelectGroup = {
  key: string;
  label: string;
  items: OrgUnitSelectOption[];
};

function groupLabelForId(groupId: number | null, groupLabelById: Map<number, string>): string {
  if (groupId == null) return "Без группы";
  if (groupLabelById.has(groupId)) return groupLabelById.get(groupId)!;
  return `Группа #${groupId}`;
}

export function buildOrgUnitSelectGroups(
  options: OrgUnitSelectOption[],
  groupLabelById: Map<number, string>,
): OrgUnitSelectGroup[] {
  const buckets = new Map<string, { label: string; items: OrgUnitSelectOption[] }>();

  for (const opt of options) {
    const gid = opt.group_id;
    const key = gid != null ? `g-${gid}` : "g-none";
    const label = groupLabelForId(gid, groupLabelById);
    if (!buckets.has(key)) buckets.set(key, { label, items: [] });
    buckets.get(key)!.items.push(opt);
  }

  const groups: OrgUnitSelectGroup[] = Array.from(buckets.entries()).map(([key, bucket]) => ({
    key,
    label: bucket.label,
    items: bucket.items.sort((a, b) => a.name.localeCompare(b.name, "ru")),
  }));

  return groups.sort((a, b) => {
    const rank = (key: string) => {
      if (key === "g-none") return 9999;
      const match = /^g-(\d+)$/.exec(key);
      return match ? Number(match[1]) : 9998;
    };
    const cmp = rank(a.key) - rank(b.key);
    if (cmp !== 0) return cmp;
    return a.label.localeCompare(b.label, "ru");
  });
}
