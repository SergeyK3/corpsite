// FILE: corpsite-ui/components/OrgUnitsSidebarPanel.tsx
"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { apiFetchJson } from "@/lib/api";

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

function nodeKey(raw: ApiOrgUnitNode): string {
  const v = raw?.id ?? raw?.code ?? raw?.unit_id ?? raw?.unitId;
  return String(v ?? "").trim() || "unknown";
}

function nodeTitle(raw: ApiOrgUnitNode): string {
  return String(raw?.title ?? raw?.name ?? raw?.code ?? raw?.id ?? "—").trim() || "—";
}

function nodeGroupId(raw: ApiOrgUnitNode): number | null {
  const g = raw?.group_id ?? raw?.groupId;
  return typeof g === "number" && Number.isFinite(g) ? g : null;
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
  const nodes = itemsRaw.map((x) => ({
    raw: x,
    key: nodeKey(x),
    unit_id: (() => {
      const u = x?.unit_id ?? x?.unitId;
      if (typeof u === "number" && Number.isFinite(u)) return u;
      const n = Number(x?.id);
      return Number.isFinite(n) ? n : null;
    })(),
    name: nodeTitle(x),
    group_id: nodeGroupId(x),
  }));

  const byKey = new Map<string, OrgTreeNode>();
  nodes.forEach((n) =>
    byKey.set(n.key, {
      key: n.key,
      unit_id: n.unit_id,
      name: n.name,
      group_id: n.group_id,
      children: [],
    })
  );

  const parentOf = (x: ApiOrgUnitNode): string | null => {
    const p = x?.parentId ?? x?.parent_id ?? x?.parent_unit_id ?? x?.parentUnitId;
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

const GROUP_NAMES: Record<number, string> = {
  1: "Клинические",
  2: "Параклинические",
  3: "Адмхоз",
};

const HIDDEN_VISIBLE_ROOT_NAME = "Многопрофильный медицинский центр";

function groupChildrenByGroupId(children: OrgTreeNode[]): OrgTreeNode[] {
  const buckets = new Map<number, OrgTreeNode[]>();
  const rest: OrgTreeNode[] = [];

  for (const ch of children) {
    const gid = ch.group_id;
    if (gid && GROUP_NAMES[gid]) {
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
      name: GROUP_NAMES[gid] ?? `Группа ${gid}`,
      group_id: gid,
      children: (buckets.get(gid) ?? []).sort((a, b) =>
        normalizeText(a.name).localeCompare(normalizeText(b.name), "ru")
      ),
    }));

  const restSorted = rest.sort((a, b) =>
    normalizeText(a.name).localeCompare(normalizeText(b.name), "ru")
  );

  return [...grouped, ...restSorted];
}

function injectGroupsIfPossible(tree: OrgTreeNode[]): OrgTreeNode[] {
  if (!Array.isArray(tree) || tree.length === 0) return tree;

  if (tree.length === 1 && Array.isArray(tree[0].children) && tree[0].children.length > 0) {
    const root = tree[0];
    const hasGroupIds = root.children.some((c) => !!c.group_id && !!GROUP_NAMES[c.group_id]);
    const alreadyGrouped = root.children.some((c) => c.key.startsWith("group-"));

    if (hasGroupIds && !alreadyGrouped) {
      const nextChildren = groupChildrenByGroupId(root.children);
      return [{ ...root, children: nextChildren }];
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

async function fetchOrgTree(extraHeaders: Record<string, string>): Promise<OrgTreeNode[]> {
  const raw = await apiFetchJson<ApiOrgUnitsTreeResponse>("/directory/org-units/tree", {
    method: "GET",
    headers: extraHeaders,
  });

  const itemsRaw = Array.isArray(raw?.items) ? raw.items : [];

  const looksTree = itemsRaw.some((x) => Array.isArray(x?.children) && (x.children?.length ?? 0) > 0);
  if (looksTree) {
    return stripVisibleRootIfNeeded(injectGroupsIfPossible(itemsRaw.map(normalizeOrgUnitNodeTree)));
  }

  const flatHasParents = itemsRaw.some(
    (x) => x?.parentId != null || x?.parent_id != null || x?.parent_unit_id != null || x?.parentUnitId != null
  );
  if (flatHasParents) {
    return stripVisibleRootIfNeeded(injectGroupsIfPossible(buildTreeFromFlat(itemsRaw)));
  }

  return stripVisibleRootIfNeeded(injectGroupsIfPossible(itemsRaw.map(normalizeOrgUnitNodeTree)));
}

export default function OrgUnitsSidebarPanel({ basePath }: { basePath: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const appEnv = (process.env.NEXT_PUBLIC_APP_ENV || "dev").trim().toLowerCase();
  const devUserId =
    appEnv === "prod" || appEnv === "production"
      ? ""
      : (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  const extraHeaders = React.useMemo(() => {
    const h: Record<string, string> = { Accept: "application/json" };
    if (devUserId) h["X-User-Id"] = devUserId;
    return h;
  }, [devUserId]);

  const selectedId = React.useMemo(() => parseIntOrNull(sp.get("org_unit_id")), [sp]);

  const [q, setQ] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [err, setErr] = React.useState<string | null>(null);
  const [items, setItems] = React.useState<OrgTreeNode[]>([]);
  const [expanded, setExpanded] = React.useState<Set<string>>(() => new Set());

  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      setLoading(true);
      setErr(null);
      try {
        const data = await fetchOrgTree(extraHeaders);
        if (cancelled) return;

        const nextItems = Array.isArray(data) ? data : [];
        setItems(nextItems);

        setExpanded(() => {
          const opened = new Set<string>();

          for (const n of nextItems) {
            if (n.key.startsWith("group-")) {
              opened.add(n.key);
            }
          }

          return opened;
        });
      } catch (e: any) {
        if (cancelled) return;
        setErr(String(e?.message ?? e ?? "Ошибка загрузки дерева"));
        setItems([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [extraHeaders]);

  function replaceUrl(next: Partial<Record<string, string | null>>) {
    const p = new URLSearchParams(sp.toString());

    Object.entries(next).forEach(([k, v]) => {
      const s = (v ?? "").toString().trim();
      if (!s) p.delete(k);
      else p.set(k, s);
    });

    const targetPath = (pathname || "").trim() || (basePath || "").trim() || "/directory/roles";
    const qs = p.toString();
    router.replace(qs ? `${targetPath}?${qs}` : targetPath);
    router.refresh();
  }

  function toggle(key: string) {
    setExpanded((prev) => {
      const n = new Set(prev);
      if (n.has(key)) n.delete(key);
      else n.add(key);
      return n;
    });
  }

  function matchesFilter(name: string) {
    const fq = normalizeText(q);
    if (!fq) return true;
    return normalizeText(name).includes(fq);
  }

  function filterTree(nodes: OrgTreeNode[]): OrgTreeNode[] {
    const walk = (n: OrgTreeNode): OrgTreeNode | null => {
      const kids = (n.children || []).map(walk).filter(Boolean) as OrgTreeNode[];
      const ok = matchesFilter(n.name) || kids.length > 0;
      return ok ? { ...n, children: kids } : null;
    };
    return nodes.map(walk).filter(Boolean) as OrgTreeNode[];
  }

  const filtered = React.useMemo(() => filterTree(items), [items, q]);

  function renderNode(n: OrgTreeNode, depth: number) {
    const hasChildren = Array.isArray(n.children) && n.children.length > 0;
    const isOpen = expanded.has(n.key);
    const isSelected = selectedId != null && n.unit_id === selectedId;
    const selectable = n.unit_id != null;

    return (
      <div key={n.key}>
        <div
          className={[
            "flex items-center gap-2 rounded-lg border px-2 py-1 text-sm",
            "border-zinc-800 bg-zinc-950/40 hover:bg-zinc-900/60",
            isSelected ? "border-zinc-600 bg-zinc-900/60" : "",
          ].join(" ")}
          style={{ paddingLeft: 8 + depth * 10 }}
        >
          {hasChildren ? (
            <button
              type="button"
              onClick={() => toggle(n.key)}
              className="h-5 w-5 rounded-md border border-zinc-800 bg-zinc-950/40 text-[11px] text-zinc-200 hover:bg-zinc-900/60"
              aria-label={isOpen ? "Свернуть" : "Развернуть"}
              title={isOpen ? "Свернуть" : "Развернуть"}
            >
              {isOpen ? "▾" : "▸"}
            </button>
          ) : (
            <span className="inline-block h-5 w-5" />
          )}

          <button
            type="button"
            className={[
              "min-w-0 flex-1 truncate text-left",
              selectable ? "text-zinc-100" : "text-zinc-300",
            ].join(" ")}
            onClick={() => {
              if (!selectable) {
                if (hasChildren) toggle(n.key);
                return;
              }

              replaceUrl({
                org_unit_id: String(n.unit_id),
                org_unit_name: n.name,
              });
            }}
            title={n.name}
          >
            {n.name}
          </button>
        </div>

        {hasChildren && isOpen ? (
          <div className="mt-1 space-y-1">{n.children.map((c) => renderNode(c, depth + 1))}</div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-2.5">
      <div className="mb-2 text-sm font-semibold text-zinc-100">Отделения</div>

      <div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Поиск по отделениям"
          className="w-full rounded-md border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 outline-none"
        />
      </div>

      <div className="mt-3 max-h-[calc(100vh-260px)] space-y-1 overflow-auto pr-1">
        {loading ? <div className="text-sm text-zinc-400">Загрузка…</div> : null}
        {err ? <div className="text-sm text-red-400">Ошибка: {err}</div> : null}

        {!loading && !err ? filtered.map((n) => renderNode(n, 0)) : null}

        {!loading && !err && filtered.length === 0 ? (
          <div className="text-sm text-zinc-400">Ничего не найдено.</div>
        ) : null}
      </div>
    </div>
  );
}