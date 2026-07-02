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
  group_id?: number | null;
  groupId?: number | null;
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
  if (typeof g === "number" && Number.isFinite(g) && g > 0) return g;
  return null;
}

function dedupeOrgUnitOptions(items: OrgUnitSelectOption[]): OrgUnitSelectOption[] {
  const seen = new Set<number>();
  return items
    .filter((x) => {
      if (seen.has(x.unit_id)) return false;
      seen.add(x.unit_id);
      return true;
    })
    .sort((a, b) => a.name.localeCompare(b.name, "ru"));
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
): OrgTreeNode[] {
  const buckets = new Map<number, OrgTreeNode[]>();
  const rest: OrgTreeNode[] = [];

  for (const ch of children) {
    const gid = ch.group_id;
    if (gid && groupLabelById.has(gid)) {
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
    const hasGroupIds = root.children.some((c) => !!c.group_id && groupLabelById.has(c.group_id));
    const alreadyGrouped = root.children.some((c) => c.key.startsWith("group-"));

    if (hasGroupIds && !alreadyGrouped) {
      return [{ ...root, children: groupChildrenByGroupId(root.children, groupLabelById) }];
    }
  }

  return tree;
}

function stripVisibleRootIfNeeded(tree: OrgTreeNode[]): OrgTreeNode[] {
  if (!Array.isArray(tree) || tree.length !== 1) return tree;

  const root = tree[0];
  const hasChildren = Array.isArray(root.children) && root.children.length > 0;
  if (!hasChildren) return tree;

  if (normalizeText(root.name) === normalizeText(HIDDEN_VISIBLE_ROOT_NAME)) {
    return root.children;
  }

  return tree;
}

function prepareOrgTree(itemsRaw: OrgUnitRow[], groupLabelById: Map<number, string>): OrgTreeNode[] {
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

  return stripVisibleRootIfNeeded(injectGroupsIfPossible(tree, groupLabelById));
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

export async function loadOrgUnitSelectOptions(): Promise<OrgUnitSelectOption[]> {
  const groupLabelById = await loadDepartmentGroupLabelMap();
  const collected: OrgUnitSelectOption[][] = [];

  try {
    const tree = await apiFetchJson<{ items?: OrgUnitRow[] }>("/directory/org-units/tree", {
      query: { status: "active" },
    });
    const itemsRaw = Array.isArray(tree?.items) ? tree.items : [];
    if (itemsRaw.length > 0) {
      collected.push(flattenOrgUnitTree(prepareOrgTree(itemsRaw, groupLabelById)));
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
