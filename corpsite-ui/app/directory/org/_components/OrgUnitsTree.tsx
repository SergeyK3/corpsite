// FILE: corpsite-ui/app/directory/org/_components/OrgUnitsTree.tsx
"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { apiFetchJson } from "../../../../lib/api";

type ApiOrgUnitNode = {
  id?: string | number;
  code?: string;
  unit_id?: number;
  unitId?: number;

  title?: string;
  name?: string;

  parent_id?: string | number | null;
  parentId?: string | number | null;
  parent_unit_id?: number | null;
  parentUnitId?: number | null;

  group_id?: number | null;
  groupId?: number | null;

  children?: ApiOrgUnitNode[];
};

type ApiOrgUnitsTreeResponse = {
  items?: ApiOrgUnitNode[];
  total?: number;
  root_id?: string | number | null;
};

type OrgTreeNode = {
  key: string;
  unit_id: number | null;
  name: string;
  group_id: number | null;
  children: OrgTreeNode[];
};

function getDevUserId(): string | null {
  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
  if (appEnv === "prod" || appEnv === "production") return null;
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v ? v : null;
}

function normalizeText(v: any): string {
  return String(v ?? "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/[ё]/g, "е")
    .trim();
}

function parseIntOrNull(v: string | null): number | null {
  if (!v) return null;
  const n = Number(String(v).trim());
  return Number.isFinite(n) ? n : null;
}

function parseSet(raw: string | null): Set<string> {
  const out = new Set<string>();
  const s = (raw || "").trim();
  if (!s) return out;
  for (const part of s.split(",")) {
    const k = String(part).trim();
    if (k) out.add(k);
  }
  return out;
}

function serializeSet(set: Set<string>): string {
  const arr = Array.from(set.values()).filter((x) => String(x).trim().length > 0);
  arr.sort((a, b) => a.localeCompare(b));
  return arr.join(",");
}

function nodeKey(raw: ApiOrgUnitNode): string {
  const v = raw?.id ?? raw?.code ?? raw?.unit_id ?? raw?.unitId;
  return String(v ?? "").trim() || "unknown";
}

function nodeTitle(raw: ApiOrgUnitNode): string {
  return String(raw?.title ?? raw?.name ?? raw?.code ?? raw?.id ?? "—").trim() || "—";
}

function nodeGroupId(raw: ApiOrgUnitNode): number | null {
  const g = raw?.group_id ?? raw?.groupId;
  if (typeof g === "number" && Number.isFinite(g)) return g;
  const n = Number(g);
  return Number.isFinite(n) ? n : null;
}

function normalizeOrgUnitNodeTree(raw: ApiOrgUnitNode): OrgTreeNode {
  const key = nodeKey(raw);

  const unit_id = (() => {
    const u = raw?.unit_id ?? raw?.unitId;
    if (typeof u === "number" && Number.isFinite(u)) return u;
    const n = Number(raw?.id);
    return Number.isFinite(n) ? n : null;
  })();

  const group_id = nodeGroupId(raw);

  const childrenRaw = Array.isArray(raw?.children) ? raw.children : [];
  const children = childrenRaw.map(normalizeOrgUnitNodeTree);

  return { key, unit_id, name: nodeTitle(raw), group_id, children };
}

function buildTreeFromFlat(itemsRaw: ApiOrgUnitNode[]): OrgTreeNode[] {
  const byKey = new Map<string, OrgTreeNode>();

  for (const x of itemsRaw) {
    const k = nodeKey(x);
    const unit_id = (() => {
      const u = x?.unit_id ?? x?.unitId;
      if (typeof u === "number" && Number.isFinite(u)) return u;
      const n = Number(x?.id);
      return Number.isFinite(n) ? n : null;
    })();

    byKey.set(k, { key: k, unit_id, name: nodeTitle(x), group_id: nodeGroupId(x), children: [] });
  }

  const parentOf = (x: ApiOrgUnitNode): string | null => {
    const p = x?.parentId ?? x?.parent_id ?? x?.parent_unit_id ?? x?.parentUnitId;
    if (p === null || p === undefined) return null;
    return String(p).trim() || null;
  };

  const roots: OrgTreeNode[] = [];
  for (const x of itemsRaw) {
    const k = nodeKey(x);
    const p = parentOf(x);
    const cur = byKey.get(k)!;
    if (p && byKey.has(p)) byKey.get(p)!.children.push(cur);
    else roots.push(cur);
  }
  return roots;
}

async function fetchOrgTree(extraHeaders: Record<string, string>): Promise<OrgTreeNode[]> {
  const raw = await apiFetchJson<ApiOrgUnitsTreeResponse>("/directory/org-units/tree", {
    method: "GET",
    headers: extraHeaders,
  });

  const itemsRaw = Array.isArray(raw?.items) ? raw.items : [];
  const looksTree = itemsRaw.some((x) => Array.isArray(x?.children) && (x.children?.length ?? 0) > 0);

  if (looksTree) return itemsRaw.map(normalizeOrgUnitNodeTree);

  const flatHasParents = itemsRaw.some(
    (x) => x?.parentId != null || x?.parent_id != null || x?.parent_unit_id != null || x?.parentUnitId != null
  );

  if (flatHasParents) return buildTreeFromFlat(itemsRaw);

  return itemsRaw.map(normalizeOrgUnitNodeTree);
}

function buildParentMap(nodes: OrgTreeNode[]): Map<string, string | null> {
  const parent = new Map<string, string | null>();
  const walk = (n: OrgTreeNode, p: string | null) => {
    parent.set(n.key, p);
    (n.children || []).forEach((ch) => walk(ch, n.key));
  };
  nodes.forEach((n) => walk(n, null));
  return parent;
}

function ancestorsOf(key: string, parentMap: Map<string, string | null>): string[] {
  const out: string[] = [];
  let cur: string | null | undefined = key;
  while (cur != null) {
    const p = parentMap.get(cur);
    if (p == null) break;
    out.push(p);
    cur = p;
  }
  return out;
}

function filterOrgTree(nodes: OrgTreeNode[], termRaw: string): OrgTreeNode[] {
  const term = normalizeText(termRaw);
  if (!term) return nodes;

  const walk = (n: OrgTreeNode): OrgTreeNode | null => {
    const nameMatch = normalizeText(n.name).includes(term);
    const keptChildren: OrgTreeNode[] = [];

    for (const ch of n.children || []) {
      const r = walk(ch);
      if (r) keptChildren.push(r);
    }

    if (nameMatch || keptChildren.length > 0) return { ...n, children: keptChildren };
    return null;
  };

  const out: OrgTreeNode[] = [];
  for (const n of nodes) {
    const r = walk(n);
    if (r) out.push(r);
  }
  return out;
}

function groupLabel(groupId: number | null): string {
  if (groupId === 1) return "Клинические";
  if (groupId === 2) return "Параклинические";
  if (groupId === 3) return "Адмхоз";
  return "Другое";
}

function groupRank(groupId: number | null): number {
  if (groupId === 1) return 10;
  if (groupId === 2) return 20;
  if (groupId === 3) return 30;
  return 99;
}

// Чтобы группа стабильно идентифицировалась в URL
function groupKeyByRank(rank: number): string {
  if (rank === 10) return "g1";
  if (rank === 20) return "g2";
  if (rank === 30) return "g3";
  return `g${rank}`;
}

function buildKeyMaps(nodes: OrgTreeNode[]): { keyByUnitId: Map<number, string>; nodeByKey: Map<string, OrgTreeNode> } {
  const keyByUnitId = new Map<number, string>();
  const nodeByKey = new Map<string, OrgTreeNode>();

  const walk = (n: OrgTreeNode) => {
    nodeByKey.set(n.key, n);
    if (typeof n.unit_id === "number" && Number.isFinite(n.unit_id)) keyByUnitId.set(n.unit_id, n.key);
    (n.children || []).forEach(walk);
  };
  nodes.forEach(walk);
  return { keyByUnitId, nodeByKey };
}

/**
 * Возвращает "групповой" узел (тот, который лежит на уровне группировки, т.е. depth=1).
 * Типовая структура: один корень (ORG_MAIN) -> его дети (group_id=1/2/3) -> далее подразделения.
 */
function groupNodeKeyForSelected(opts: {
  selectedKey: string;
  parentMap: Map<string, string | null>;
}): string {
  const { selectedKey, parentMap } = opts;

  let cur = selectedKey;

  // поднимаемся пока не придем к узлу, чей родитель имеет parent=null (то есть это "ребенок корня")
  while (true) {
    const p = parentMap.get(cur) ?? null;
    if (p == null) return cur; // сам корень или одиночный кейс
    const pp = parentMap.get(p) ?? null;
    if (pp == null) return cur; // cur — ребенок корня (depth=1)
    cur = p;
  }
}

export default function OrgUnitsTree() {
  const router = useRouter();
  const sp = useSearchParams();
  const devUserId = getDevUserId();

  const extraHeaders = React.useMemo(() => {
    const h: Record<string, string> = { Accept: "application/json" };
    if (devUserId) h["X-User-Id"] = devUserId;
    return h;
  }, [devUserId]);

  const urlOrgUnitId = React.useMemo(() => parseIntOrNull(sp.get("org_unit_id")), [sp]);
  const urlExpanded = React.useMemo(() => parseSet(sp.get("expanded")), [sp]);

  // группы: по умолчанию пусто => все свернуты
  const urlGroupsOpen = React.useMemo(() => parseSet(sp.get("groups")), [sp]);

  const [orgLoading, setOrgLoading] = React.useState(false);
  const [orgError, setOrgError] = React.useState<string | null>(null);
  const [orgItems, setOrgItems] = React.useState<OrgTreeNode[]>([]);
  const [filterText, setFilterText] = React.useState("");

  const [expandedSet, setExpandedSet] = React.useState<Set<string>>(new Set<string>());
  const [groupsOpenSet, setGroupsOpenSet] = React.useState<Set<string>>(new Set<string>());

  React.useEffect(() => {
    setExpandedSet(new Set<string>(Array.from(urlExpanded.values())));
  }, [urlExpanded]);

  React.useEffect(() => {
    setGroupsOpenSet(new Set<string>(Array.from(urlGroupsOpen.values())));
  }, [urlGroupsOpen]);

  const parentMap = React.useMemo(() => buildParentMap(orgItems), [orgItems]);
  const { keyByUnitId, nodeByKey } = React.useMemo(() => buildKeyMaps(orgItems), [orgItems]);

  function replaceUrl(next: Partial<Record<string, string | null>>) {
    const p = new URLSearchParams(sp.toString());
    Object.entries(next).forEach(([k, v]) => {
      const s = (v ?? "").toString().trim();
      if (!s) p.delete(k);
      else p.set(k, s);
    });
    router.replace(`/directory/org?${p.toString()}`);
  }

  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      setOrgLoading(true);
      setOrgError(null);
      try {
        const items = await fetchOrgTree(extraHeaders);
        if (cancelled) return;
        setOrgItems(items);
      } catch (e: any) {
        if (cancelled) return;
        setOrgError(e?.message || String(e));
        setOrgItems([]);
      } finally {
        if (!cancelled) setOrgLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [extraHeaders]);

  const searchActive = Boolean(filterText.trim());
  const treeForRender = React.useMemo(() => {
    if (!searchActive) return orgItems;
    return filterOrgTree(orgItems, filterText);
  }, [orgItems, filterText, searchActive]);

  function isExpanded(key: string): boolean {
    if (searchActive) return true;
    return expandedSet.has(key);
  }

  function toggleExpanded(key: string) {
    const next = new Set<string>(Array.from(expandedSet.values()));
    if (next.has(key)) next.delete(key);
    else next.add(key);

    setExpandedSet(next);
    replaceUrl({ expanded: serializeSet(next) });
  }

  /**
   * Раскрывает:
   * - цепочку родителей (expanded)
   * - нужную группу (groups), чтобы выбранный узел был виден даже при "свернутых группах по умолчанию"
   */
  function ensureExpandedForSelectionByKey(key: string, opts?: { syncUrl?: boolean }) {
    const syncUrl = opts?.syncUrl !== false; // default true

    // expanded
    const nextExpanded = new Set<string>(Array.from(expandedSet.values()));
    ancestorsOf(key, parentMap).forEach((x) => nextExpanded.add(x));
    nextExpanded.add(key);

    // groups (открываем группу уровня depth=1)
    const gNodeKey = groupNodeKeyForSelected({ selectedKey: key, parentMap });
    const gNode = nodeByKey.get(gNodeKey);
    const gk = groupKeyByRank(groupRank(gNode?.group_id ?? null));

    const nextGroups = new Set<string>(Array.from(groupsOpenSet.values()));
    nextGroups.add(gk);

    setExpandedSet(nextExpanded);
    setGroupsOpenSet(nextGroups);

    if (syncUrl) {
      replaceUrl({
        expanded: serializeSet(nextExpanded),
        groups: serializeSet(nextGroups),
      });
    }
  }

  function onSelectUnit(n: OrgTreeNode) {
    ensureExpandedForSelectionByKey(n.key, { syncUrl: true });
    replaceUrl({ org_unit_id: n.unit_id != null ? String(n.unit_id) : null });
  }

  // Автораскрытие при заходе по ссылке с org_unit_id
  React.useEffect(() => {
    if (searchActive) return;
    if (urlOrgUnitId == null) return;
    if (orgItems.length === 0) return;

    const k = keyByUnitId.get(urlOrgUnitId);
    if (!k) return;

    ensureExpandedForSelectionByKey(k, { syncUrl: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlOrgUnitId, orgItems.length, searchActive, keyByUnitId]);

  function isGroupOpen(groupKey: string): boolean {
    if (searchActive) return true; // поиск раскрывает все группы
    return groupsOpenSet.has(groupKey);
  }

  function toggleGroup(groupKey: string) {
    const next = new Set<string>(Array.from(groupsOpenSet.values()));
    if (next.has(groupKey)) next.delete(groupKey);
    else next.add(groupKey);

    setGroupsOpenSet(next);
    replaceUrl({ groups: serializeSet(next) });
  }

  function renderTree(nodes: OrgTreeNode[], depth: number): React.ReactNode {
    const sortByName = (arr: OrgTreeNode[]) =>
      [...arr].sort((a, b) => (a.name || "").localeCompare(b.name || "", "ru"));

    const shouldGroup = depth === 1 || (depth === 0 && nodes.length > 1);

    if (shouldGroup) {
      const buckets = new Map<number, OrgTreeNode[]>();
      for (const n of nodes) {
        const r = groupRank(n.group_id);
        if (!buckets.has(r)) buckets.set(r, []);
        buckets.get(r)!.push(n);
      }

      const ranks = Array.from(buckets.keys()).sort((a, b) => a - b);

      return ranks.map((r) => {
        const chunk = sortByName(buckets.get(r)!);
        const label = groupLabel(chunk[0]?.group_id ?? null);

        const gk = groupKeyByRank(r);
        const open = isGroupOpen(gk);

        return (
          <div key={`group-${depth}-${r}`} className="mb-3">
            <button
              type="button"
              className="mb-2 flex w-full items-center justify-between rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-left text-xs font-semibold text-zinc-200 hover:bg-zinc-900/60"
              onClick={() => toggleGroup(gk)}
              aria-expanded={open}
              title={open ? "Свернуть группу" : "Развернуть группу"}
            >
              <span>{label}</span>
              <span className="text-xs text-zinc-300">{open ? "▾" : "▸"}</span>
            </button>

            {open ? <div className="space-y-1">{chunk.map((n) => renderTree([n], depth + 1))}</div> : null}
          </div>
        );
      });
    }

    const sorted = sortByName(nodes);

    return sorted.map((n) => {
      const hasChildren = Array.isArray(n.children) && n.children.length > 0;
      const expanded = hasChildren ? isExpanded(n.key) : false;
      const active = urlOrgUnitId != null && n.unit_id != null && urlOrgUnitId === n.unit_id;

      return (
        <div key={n.key}>
          <div className="flex items-stretch">
            <div className="flex items-center" style={{ paddingLeft: `${Math.max(0, depth - 1) * 12}px` }}>
              {hasChildren ? (
                <button
                  type="button"
                  className="mr-2 h-6 w-6 rounded border border-zinc-800 bg-zinc-950/40 text-zinc-200 hover:bg-zinc-900/60"
                  onClick={(ev) => {
                    ev.stopPropagation();
                    toggleExpanded(n.key);
                  }}
                  aria-label={expanded ? "Свернуть" : "Развернуть"}
                  title={expanded ? "Свернуть" : "Развернуть"}
                >
                  <span className="text-xs">{expanded ? "▾" : "▸"}</span>
                </button>
              ) : (
                <div className="mr-2 h-6 w-6" />
              )}
            </div>

            <button
              type="button"
              className={[
                "flex-1 rounded-lg border px-3 py-2 text-left text-sm",
                "border-zinc-800 bg-zinc-950/40 text-zinc-100 hover:bg-zinc-900/60",
                active ? "outline outline-1 outline-zinc-600" : "",
              ].join(" ")}
              onClick={() => onSelectUnit(n)}
              title={n.unit_id == null ? "Узел без numeric unit_id" : "Выбрать подразделение"}
            >
              {n.name}
            </button>
          </div>

          {hasChildren && expanded ? <div className="mt-1 space-y-1">{renderTree(n.children, depth + 1)}</div> : null}
        </div>
      );
    });
  }

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40">
      <div className="border-b border-zinc-800 p-4">
        <div className="text-sm font-semibold text-zinc-100">Отделения</div>
        <div className="mt-2">
          <input
            className="w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 outline-none"
            placeholder="Поиск по подразделениям"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
          />
        </div>
      </div>

      <div className="p-4">
        {orgError ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{orgError}</div>
        ) : null}

        {orgLoading ? <div className="text-sm text-zinc-400">Загрузка…</div> : null}

        {!orgLoading && !orgError ? (
          <div className="max-h-[70vh] space-y-1 overflow-auto">
            {treeForRender.length > 0 ? (
              renderTree(treeForRender, 0)
            ) : (
              <div className="text-sm text-zinc-400">Ничего не найдено.</div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}