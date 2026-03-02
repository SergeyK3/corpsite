// FILE: corpsite-ui/app/directory/org/_components/OrgPageClient.tsx
"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import type { EmployeeDTO, EmployeeDetails, EmployeesResponse } from "../../employees/_lib/types";

import EmployeeDrawer from "../../employees/_components/EmployeeDrawer";
import { apiFetchJson } from "../../../../lib/api";

type UnitPick = {
  key: string; // идентификатор узла в дереве (может быть строковым)
  unit_id: number | null; // числовой unit_id для запросов /directory/employees
  name: string;
};

// ---------------------------
// Backend: /directory/org-units/tree
// На практике узлы могут быть:
// - id: number | string (часто code)
// - unit_id: number (реальный bigint из БД) — может присутствовать
// - title/name
// - children
// Иногда дерево может прийти "плоским" (items + parent_id), поэтому делаем fallback.
// ---------------------------
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

  children?: ApiOrgUnitNode[];
};

type ApiOrgUnitsTreeResponse = {
  items?: ApiOrgUnitNode[];
  total?: number;
  root_id?: string | number | null;
};

type OrgTreeNode = {
  key: string; // стабильный ключ для React + expanded
  unit_id: number | null; // bigint из БД, если есть
  name: string;
  children: OrgTreeNode[];
};

type OrgTreeResponse = {
  items: OrgTreeNode[];
  total?: number;
};

function getDevUserId(): string | null {
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

function mapApiErrorToMessage(e: unknown): string {
  const anyE = e as any;

  const status =
    typeof anyE?.status === "number"
      ? anyE.status
      : (() => {
          const msg = e instanceof Error ? e.message : String(e ?? "");
          const m = msg.match(/\b(?:HTTP|failed:)\s*(\d{3})\b/i);
          return m ? Number(m[1]) : undefined;
        })();

  if (status === 401) return "Нет доступа (401).";
  if (status === 403) return "Недостаточно прав (403).";
  if (status === 404) return "Не найдено (404).";
  if (status && status >= 500) return "Ошибка сервера. Попробуйте позже.";

  const msg =
    typeof anyE?.message === "string"
      ? anyE.message
      : e instanceof Error
        ? e.message
        : String(e ?? "Unknown error");

  return msg || "Ошибка запроса.";
}

// ---------------------------
// expanded tree in URL: expanded=a,b,c (строковые ключи)
// ---------------------------
function parseExpanded(raw: string | null): Set<string> {
  const out = new Set<string>();
  const s = (raw || "").trim();
  if (!s) return out;

  for (const part of s.split(",")) {
    const k = String(part).trim();
    if (k) out.add(k);
  }
  return out;
}

function serializeExpanded(set: Set<string>): string {
  const arr = Array.from(set.values()).filter((x) => String(x).trim().length > 0);
  arr.sort((a, b) => a.localeCompare(b));
  return arr.join(",");
}

function parseIntOrNull(v: string | null): number | null {
  if (!v) return null;
  const n = Number(String(v).trim());
  return Number.isFinite(n) ? n : null;
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

    if (nameMatch || keptChildren.length > 0) {
      return { ...n, children: keptChildren };
    }
    return null;
  };

  const out: OrgTreeNode[] = [];
  for (const n of nodes) {
    const r = walk(n);
    if (r) out.push(r);
  }
  return out;
}

function flattenUnits(nodes: OrgTreeNode[]): UnitPick[] {
  const out: UnitPick[] = [];
  const walk = (n: OrgTreeNode) => {
    out.push({ key: n.key, unit_id: n.unit_id, name: n.name });
    if (Array.isArray(n.children)) n.children.forEach(walk);
  };
  nodes.forEach(walk);
  return out;
}

// ---------------------------
// Normalize API node -> OrgTreeNode
// key: строковый идентификатор дерева (id/code/unit_id)
// unit_id: числовой (unit_id/unitId/если id числовой)
// ---------------------------
function nodeKey(raw: ApiOrgUnitNode): string {
  const v = raw?.id ?? raw?.code ?? raw?.unit_id ?? raw?.unitId;
  return String(v ?? "").trim() || "unknown";
}

function nodeUnitId(raw: ApiOrgUnitNode): number | null {
  const v = raw?.unit_id ?? raw?.unitId ?? raw?.parent_unit_id ?? raw?.parentUnitId;
  if (typeof v === "number" && Number.isFinite(v)) return v;

  // иногда id бывает числом в строке
  const id = raw?.unit_id ?? raw?.unitId ?? raw?.id;
  const n = Number(id);
  return Number.isFinite(n) ? n : null;
}

function nodeTitle(raw: ApiOrgUnitNode): string {
  return String(raw?.title ?? raw?.name ?? raw?.code ?? raw?.id ?? "—").trim() || "—";
}

function normalizeOrgUnitNodeTree(raw: ApiOrgUnitNode): OrgTreeNode {
  const key = nodeKey(raw);
  const unit_id = (() => {
    const u = raw?.unit_id ?? raw?.unitId;
    if (typeof u === "number" && Number.isFinite(u)) return u;
    const n = Number(raw?.id);
    return Number.isFinite(n) ? n : null;
  })();

  const childrenRaw = Array.isArray(raw?.children) ? raw.children : [];
  const children = childrenRaw.map(normalizeOrgUnitNodeTree);

  return {
    key,
    unit_id,
    name: nodeTitle(raw),
    children,
  };
}

// fallback: если items плоский список с parent_id/parent_unit_id
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
  }));

  const byKey = new Map<string, OrgTreeNode>();
  nodes.forEach((n) => {
    byKey.set(n.key, { key: n.key, unit_id: n.unit_id, name: n.name, children: [] });
  });

  const parentOf = (x: ApiOrgUnitNode): string | null => {
    const p =
      x?.parentId ??
      x?.parent_id ??
      x?.parent_unit_id ??
      x?.parentUnitId;

    if (p === null || p === undefined) return null;
    return String(p).trim() || null;
  };

  const roots: OrgTreeNode[] = [];

  nodes.forEach((n) => {
    const pKey = parentOf(n.raw);
    const cur = byKey.get(n.key)!;

    if (pKey && byKey.has(pKey)) {
      byKey.get(pKey)!.children.push(cur);
    } else {
      roots.push(cur);
    }
  });

  return roots;
}

// ---------------------------
// API wrappers
// ---------------------------
async function fetchOrgTree(extraHeaders: Record<string, string>): Promise<OrgTreeResponse> {
  const raw = await apiFetchJson<ApiOrgUnitsTreeResponse>("/directory/org-units/tree", {
    method: "GET",
    headers: extraHeaders,
  });

  const itemsRaw = Array.isArray(raw?.items) ? raw.items : [];

  // 1) если есть children в данных — используем как дерево
  const looksTree = itemsRaw.some((x) => Array.isArray(x?.children) && (x!.children!.length > 0));
  if (looksTree) {
    return {
      items: itemsRaw.map(normalizeOrgUnitNodeTree),
      total: raw?.total,
    };
  }

  // 2) иначе пробуем собрать из плоского списка
  const flatHasParents = itemsRaw.some(
    (x) =>
      x?.parentId != null ||
      x?.parent_id != null ||
      x?.parent_unit_id != null ||
      x?.parentUnitId != null
  );

  if (flatHasParents) {
    return {
      items: buildTreeFromFlat(itemsRaw),
      total: raw?.total,
    };
  }

  // 3) иначе как есть (список верхнего уровня)
  return {
    items: itemsRaw.map(normalizeOrgUnitNodeTree),
    total: raw?.total,
  };
}

async function fetchEmployeesByOrgUnit(args: {
  extraHeaders: Record<string, string>;
  orgUnitId: number;
  status: string;
  limit: number;
  offset: number;
}): Promise<EmployeesResponse> {
  const { extraHeaders, orgUnitId, status, limit, offset } = args;

  const json = await apiFetchJson<EmployeesResponse>("/directory/employees", {
    method: "GET",
    headers: extraHeaders,
    query: {
      status,
      limit,
      offset,
      org_unit_id: orgUnitId,
    },
  });

  const items = Array.isArray((json as any)?.items) ? ((json as any).items as EmployeeDTO[]) : [];
  const total = Number((json as any)?.total ?? items.length);

  return { items, total };
}

// ---------------------------
// UI helpers
// ---------------------------
function safeFio(e: any): string {
  return e?.fio ?? e?.full_name ?? e?.fullName ?? "—";
}
function safeDept(e: any): string {
  return e?.org_unit?.name ?? e?.department?.name ?? e?.department_name ?? "—";
}
function safePos(e: any): string {
  return e?.position?.name ?? e?.position_name ?? "—";
}
function safeRate(e: any): string {
  const v = e?.rate ?? e?.employment_rate;
  if (v === null || v === undefined || v === "") return "—";
  return String(v);
}
function safeActive(e: any): string {
  const active = e?.is_active;
  if (active === true) return "активен";
  if (active === false) return "неактивен";
  const s = String(e?.status ?? "").toLowerCase();
  if (s === "active") return "активен";
  if (s === "inactive") return "неактивен";
  return "—";
}

// ---------------------------
// Sorting within org unit
// ---------------------------
type RoleRule = {
  rank: number;
  keywords: string[];
};

const DEFAULT_ROLE_ORDER: RoleRule[] = [
  { rank: 10, keywords: ["завед", "зав."] },
  { rank: 20, keywords: ["врач", "доктор"] },
  { rank: 30, keywords: ["старшая медсестра", "ст. медсестра", "старший фельдшер", "ст. фельдшер"] },
  { rank: 40, keywords: ["медсестра", "м/с", "сестра"] },
  { rank: 50, keywords: ["сестра-хозяйка", "сестра хозяйка", "с-х"] },
  { rank: 60, keywords: ["санитар", "санитарка"] },
];

function getPositionName(e: any): string {
  return e?.position?.name ?? e?.position_name ?? "";
}

function roleRankByPositionName(posName: string): number {
  const t = normalizeText(posName);
  if (!t) return 999;

  for (const rule of DEFAULT_ROLE_ORDER) {
    for (const kw of rule.keywords) {
      if (t.includes(normalizeText(kw))) return rule.rank;
    }
  }
  return 999;
}

function fioForSort(e: any): string {
  return normalizeText(safeFio(e));
}

export default function OrgPageClient() {
  const router = useRouter();
  const sp = useSearchParams();

  const devUserId = getDevUserId();

  const extraHeaders = React.useMemo(() => {
    const h: Record<string, string> = { Accept: "application/json" };
    if (devUserId) h["X-User-Id"] = devUserId;
    return h;
  }, [devUserId]);

  // URL state
  const urlOrgUnitId = React.useMemo(() => parseIntOrNull(sp.get("org_unit_id")), [sp]);
  const urlEmployeeId = React.useMemo(() => (sp.get("employee_id") || "").trim() || null, [sp]);
  const urlExpanded = React.useMemo(() => parseExpanded(sp.get("expanded")), [sp]);

  const [orgLoading, setOrgLoading] = React.useState(false);
  const [orgError, setOrgError] = React.useState<string | null>(null);
  const [orgItems, setOrgItems] = React.useState<OrgTreeNode[]>([]);
  const [filterText, setFilterText] = React.useState("");

  const [selectedUnit, setSelectedUnit] = React.useState<UnitPick | null>(null);

  const [empLoading, setEmpLoading] = React.useState(false);
  const [empError, setEmpError] = React.useState<string | null>(null);
  const [empData, setEmpData] = React.useState<EmployeesResponse>({ items: [], total: 0 });

  // expanded tree state (synced with URL)
  const [expandedSet, setExpandedSet] = React.useState<Set<string>>(new Set<string>());

  // Drawer state (управляем через URL + локальный state для UX)
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerEmployeeId, setDrawerEmployeeId] = React.useState<string | null>(null);

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
    setExpandedSet(new Set<string>(Array.from(urlExpanded.values())));
  }, [urlExpanded]);

  const parentMap = React.useMemo(() => buildParentMap(orgItems), [orgItems]);

  // 1) load org tree
  React.useEffect(() => {
    let cancelled = false;

    async function loadOrg() {
      setOrgLoading(true);
      setOrgError(null);

      try {
        const data = await fetchOrgTree(extraHeaders);
        if (cancelled) return;

        const items = Array.isArray(data?.items) ? data.items : [];
        setOrgItems(items);

        const flat = flattenUnits(items);

        // priority:
        // 1) org_unit_id from URL (числовой)
        // 2) first node with numeric unit_id
        if (urlOrgUnitId != null) {
          const found = flat.find((u) => u.unit_id === urlOrgUnitId);
          if (found) {
            setSelectedUnit(found);

            if (!sp.get("expanded")) {
              const pm = buildParentMap(items);
              const need = new Set<string>();
              ancestorsOf(found.key, pm).forEach((x) => need.add(x));
              need.add(found.key);
              replaceUrl({ expanded: serializeExpanded(need) });
            }
            return;
          }
        }

        if (!selectedUnit) {
          const firstSelectable = flat.find((u) => typeof u.unit_id === "number" && u.unit_id != null);
          const first = firstSelectable ?? flat[0];

          if (first) {
            setSelectedUnit(first);

            const next: Partial<Record<string, string | null>> = {};

            // org_unit_id пишем только если он числовой
            if (first.unit_id != null && sp.get("org_unit_id") == null) {
              next.org_unit_id = String(first.unit_id);
            }

            if (sp.get("expanded") == null) {
              const pm = buildParentMap(items);
              const need = new Set<string>();
              ancestorsOf(first.key, pm).forEach((x) => need.add(x));
              need.add(first.key);
              next.expanded = serializeExpanded(need);
            }

            if (Object.keys(next).length > 0) replaceUrl(next);
          }
        }
      } catch (e) {
        if (cancelled) return;
        setOrgError(mapApiErrorToMessage(e));
        setOrgItems([]);
      } finally {
        if (!cancelled) setOrgLoading(false);
      }
    }

    loadOrg();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extraHeaders, devUserId]);

  // 1b) sync selectedUnit from URL on navigation (по numeric unit_id)
  React.useEffect(() => {
    if (orgItems.length === 0) return;
    if (urlOrgUnitId == null) return;

    const flat = flattenUnits(orgItems);
    const found = flat.find((u) => u.unit_id === urlOrgUnitId);
    if (!found) return;

    if (selectedUnit?.unit_id !== found.unit_id) {
      setSelectedUnit(found);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlOrgUnitId, orgItems]);

  // 2) load employees by selected unit
  React.useEffect(() => {
    let cancelled = false;

    async function loadEmployees() {
      if (!selectedUnit || selectedUnit.unit_id == null) {
        setEmpData({ items: [], total: 0 });
        return;
      }

      setEmpLoading(true);
      setEmpError(null);

      try {
        const data = await fetchEmployeesByOrgUnit({
          extraHeaders,
          orgUnitId: selectedUnit.unit_id,
          status: "all",
          limit: 200,
          offset: 0,
        });

        if (cancelled) return;
        setEmpData(data);
      } catch (e) {
        if (cancelled) return;
        setEmpError(mapApiErrorToMessage(e));
        setEmpData({ items: [], total: 0 });
      } finally {
        if (!cancelled) setEmpLoading(false);
      }
    }

    loadEmployees();
    return () => {
      cancelled = true;
    };
  }, [extraHeaders, selectedUnit]);

  const sortedEmployees = React.useMemo(() => {
    const items = Array.isArray(empData?.items) ? [...empData.items] : [];
    items.sort((a: any, b: any) => {
      const ra = roleRankByPositionName(getPositionName(a));
      const rb = roleRankByPositionName(getPositionName(b));
      if (ra !== rb) return ra - rb;

      const fa = fioForSort(a);
      const fb = fioForSort(b);
      if (fa !== fb) return fa.localeCompare(fb, "ru");

      return String(a?.id ?? "").localeCompare(String(b?.id ?? ""));
    });
    return items;
  }, [empData]);

  // Drawer sync from URL
  React.useEffect(() => {
    if (urlEmployeeId) {
      setDrawerEmployeeId(urlEmployeeId);
      setDrawerOpen(true);
      return;
    }
    setDrawerOpen(false);
    setDrawerEmployeeId(null);
  }, [urlEmployeeId]);

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
    replaceUrl({ expanded: serializeExpanded(next) });
  }

  function ensureExpandedForSelection(key: string) {
    const next = new Set<string>(Array.from(expandedSet.values()));
    ancestorsOf(key, parentMap).forEach((x) => next.add(x));
    next.add(key);

    setExpandedSet(next);
    replaceUrl({ expanded: serializeExpanded(next) });
  }

  function onSelectUnit(u: UnitPick) {
    setSelectedUnit(u);
    ensureExpandedForSelection(u.key);

    // org_unit_id пишем/обновляем только если он числовой
    replaceUrl({
      org_unit_id: u.unit_id != null ? String(u.unit_id) : null,
      employee_id: null,
    });
  }

  function openEmployeeDrawer(employeeId: string) {
    const id = String(employeeId ?? "").trim();
    if (!id) return;

    setDrawerEmployeeId(id);
    setDrawerOpen(true);

    replaceUrl({
      org_unit_id: selectedUnit?.unit_id != null ? String(selectedUnit.unit_id) : sp.get("org_unit_id") || null,
      employee_id: id,
    });
  }

  function closeEmployeeDrawer() {
    setDrawerOpen(false);
    setDrawerEmployeeId(null);
    replaceUrl({ employee_id: null });
  }

  async function onTerminate(_details: EmployeeDetails) {
    closeEmployeeDrawer();
  }

  function renderTree(nodes: OrgTreeNode[], depth: number): React.ReactNode {
    const sorted = [...nodes].sort((a, b) => (a.name || "").localeCompare(b.name || "", "ru"));

    return sorted.map((n) => {
      const hasChildren = Array.isArray(n.children) && n.children.length > 0;
      const expanded = hasChildren ? isExpanded(n.key) : false;

      const active =
        (selectedUnit?.key && selectedUnit.key === n.key) ||
        (selectedUnit?.unit_id != null && n.unit_id != null && selectedUnit.unit_id === n.unit_id);

      return (
        <div key={n.key}>
          <div className="flex items-stretch">
            <div className="flex items-center" style={{ paddingLeft: `${Math.max(0, depth) * 12}px` }}>
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
              onClick={() => onSelectUnit({ key: n.key, unit_id: n.unit_id, name: n.name })}
              title={n.unit_id == null ? "Узел без numeric unit_id (только для навигации)" : "Выбрать подразделение"}
            >
              {n.name}
            </button>
          </div>

          {hasChildren && expanded ? (
            <div className="mt-1 space-y-1">{renderTree(n.children, depth + 1)}</div>
          ) : null}
        </div>
      );
    });
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      {/* LEFT: tree */}
      <div className="lg:col-span-5">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40">
          <div className="border-b border-zinc-800 p-4">
            <div className="text-sm font-semibold text-zinc-100">Подразделения</div>
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
              <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {orgError}
              </div>
            ) : null}

            {orgLoading ? <div className="text-sm text-zinc-400">Загрузка…</div> : null}

            {!orgLoading && !orgError ? (
              <div className="max-h-[70vh] space-y-1 overflow-auto">
                {treeForRender.length > 0 ? renderTree(treeForRender, 0) : (
                  <div className="text-sm text-zinc-400">Ничего не найдено.</div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      {/* RIGHT: employees */}
      <div className="lg:col-span-7">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40">
          <div className="border-b border-zinc-800 p-4">
            <div className="text-sm font-semibold text-zinc-100">
              {selectedUnit ? selectedUnit.name : "Сотрудники"}
            </div>
            <div className="mt-1 text-xs text-zinc-400">
              {!selectedUnit ? (
                "Выберите подразделение слева."
              ) : selectedUnit.unit_id == null ? (
                "Это узел навигации. Выберите дочернее подразделение."
              ) : (
                `Сотрудников: ${empData.total}`
              )}
            </div>
          </div>

          <div className="p-4">
            {empError ? (
              <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {empError}
              </div>
            ) : null}

            {empLoading ? <div className="text-sm text-zinc-400">Загрузка…</div> : null}

            {!empLoading && !empError ? (
              <div className="overflow-auto rounded-xl border border-zinc-800">
                <table className="min-w-full text-sm text-zinc-100">
                  <thead className="bg-zinc-950/40 text-xs text-zinc-400">
                    <tr>
                      <th className="border-b border-zinc-800 p-2 text-left font-semibold">Таб. №</th>
                      <th className="border-b border-zinc-800 p-2 text-left font-semibold">ФИО</th>
                      <th className="border-b border-zinc-800 p-2 text-left font-semibold">Подразделение</th>
                      <th className="border-b border-zinc-800 p-2 text-left font-semibold">Должность</th>
                      <th className="border-b border-zinc-800 p-2 text-left font-semibold">Ставка</th>
                      <th className="border-b border-zinc-800 p-2 text-left font-semibold">Статус</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedEmployees.map((e: any) => {
                      const id = String(e?.id ?? "");
                      const isSelected = drawerEmployeeId && id === drawerEmployeeId;

                      return (
                        <tr
                          key={id || `${safeFio(e)}-${safePos(e)}-${safeDept(e)}`}
                          className={[
                            "cursor-pointer hover:bg-zinc-900/60",
                            isSelected ? "bg-zinc-900/60" : "",
                          ].join(" ")}
                          role="button"
                          tabIndex={0}
                          onClick={() => openEmployeeDrawer(id)}
                          onKeyDown={(ev) => {
                            if (ev.key === "Enter" || ev.key === " ") {
                              ev.preventDefault();
                              openEmployeeDrawer(id);
                            }
                          }}
                          title="Открыть карточку сотрудника"
                        >
                          <td className="border-b border-zinc-800 p-2 whitespace-nowrap">{id}</td>
                          <td className="border-b border-zinc-800 p-2">{safeFio(e)}</td>
                          <td className="border-b border-zinc-800 p-2">{safeDept(e)}</td>
                          <td className="border-b border-zinc-800 p-2">{safePos(e)}</td>
                          <td className="border-b border-zinc-800 p-2 whitespace-nowrap">{safeRate(e)}</td>
                          <td className="border-b border-zinc-800 p-2 whitespace-nowrap">{safeActive(e)}</td>
                        </tr>
                      );
                    })}

                    {sortedEmployees.length === 0 ? (
                      <tr>
                        <td className="p-3 text-zinc-400" colSpan={6}>
                          Нет сотрудников в выбранном подразделении.
                        </td>
                      </tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <EmployeeDrawer
        employeeId={drawerEmployeeId}
        open={drawerOpen}
        onClose={closeEmployeeDrawer}
        onTerminate={onTerminate}
      />
    </div>
  );
}