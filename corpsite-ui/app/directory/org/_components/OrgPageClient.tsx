// corpsite-ui/app/directory/org/_components/OrgPageClient.tsx
"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import type {
  OrgTreeNode,
  OrgTreeResponse,
  EmployeeDTO,
  EmployeesResponse,
  EmployeeDetails,
} from "../../employees/_lib/types";

import EmployeeDrawer from "../../employees/_components/EmployeeDrawer";

type UnitPick = {
  unit_id: number;
  name: string;
};

function getApiBase(): string {
  const v = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim().replace(/\/+$/, "");
  return v || "http://127.0.0.1:8000";
}

function getDevUserId(): string | null {
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v ? v : null;
}

function mapApiErrorToMessage(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e ?? "Unknown error");
  const mStatus = msg.match(/\b(?:HTTP|failed:)\s*(\d{3})\b/i);
  const status = mStatus ? Number(mStatus[1]) : undefined;

  if (status === 401) return "Нет доступа (401).";
  if (status === 403) return "Недостаточно прав (403).";
  if (status === 404) return "Не найдено (404).";
  if (status && status >= 500) return "Ошибка сервера. Попробуйте позже.";
  return msg || "Ошибка запроса.";
}

function buildQuery(params: Record<string, string | number | null | undefined>): string {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null) return;
    const s = String(v).trim();
    if (!s) return;
    q.set(k, s);
  });
  return q.toString();
}

function flattenUnits(nodes: OrgTreeNode[]): UnitPick[] {
  const out: UnitPick[] = [];
  const walk = (n: OrgTreeNode) => {
    out.push({ unit_id: n.unit_id, name: n.name });
    if (Array.isArray(n.children)) n.children.forEach(walk);
  };
  nodes.forEach(walk);
  return out;
}

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
function safeStatus(e: any): string {
  const s = String(e?.status ?? "").toLowerCase();
  if (s === "active") return "Работает";
  if (s === "inactive") return "Не работает";
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
  // 1) заведующий
  { rank: 10, keywords: ["завед", "зав."] },

  // 2) врачи (прочие)
  { rank: 20, keywords: ["врач", "доктор"] },

  // 3) старшая медсестра / старший фельдшер
  {
    rank: 30,
    keywords: ["старшая медсестра", "ст. медсестра", "старший фельдшер", "ст. фельдшер"],
  },

  // 4) прочие медсестры (детализацию уточним позже)
  { rank: 40, keywords: ["медсестра", "м/с", "сестра"] },

  // 5) сестра-хозяйка
  { rank: 50, keywords: ["сестра-хозяйка", "сестра хозяйка", "с-х"] },

  // 6) санитарки
  { rank: 60, keywords: ["санитар", "санитарка"] },
];

function normalizeText(v: any): string {
  return String(v ?? "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/[ё]/g, "е")
    .trim();
}

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

// ---------------------------
// Expanded tree in URL
// expanded=44,28,29
// ---------------------------
function parseExpanded(raw: string | null): Set<number> {
  const out = new Set<number>();
  const s = (raw || "").trim();
  if (!s) return out;

  for (const part of s.split(",")) {
    const n = Number(String(part).trim());
    if (Number.isFinite(n)) out.add(n);
  }
  return out;
}

function serializeExpanded(set: Set<number>): string {
  const arr = Array.from(set.values()).filter((n) => Number.isFinite(n));
  arr.sort((a, b) => a - b);
  return arr.join(",");
}

function buildParentMap(nodes: OrgTreeNode[]): Map<number, number | null> {
  const parent = new Map<number, number | null>();
  const walk = (n: OrgTreeNode, p: number | null) => {
    parent.set(n.unit_id, p);
    (n.children || []).forEach((ch) => walk(ch, n.unit_id));
  };
  nodes.forEach((n) => walk(n, null));
  return parent;
}

function ancestorsOf(unitId: number, parentMap: Map<number, number | null>): number[] {
  const out: number[] = [];
  let cur: number | null | undefined = unitId;

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
    const children = Array.isArray(n.children) ? n.children : [];

    const keptChildren: OrgTreeNode[] = [];
    for (const ch of children) {
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

function parseIntOrNull(v: string | null): number | null {
  if (!v) return null;
  const n = Number(String(v).trim());
  return Number.isFinite(n) ? n : null;
}

// ---------------------------
// Backend fetch
// ---------------------------
async function fetchEmployeesByOrgUnit(args: {
  apiBase: string;
  headers: Record<string, string>;
  orgUnitId: number;
  status: string;
  limit: number;
  offset: number;
}): Promise<EmployeesResponse> {
  const { apiBase, headers, orgUnitId, status, limit, offset } = args;

  const qs = buildQuery({
    status,
    limit,
    offset,
    org_unit_id: orgUnitId,
  });

  const res = await fetch(`${apiBase}/directory/employees?${qs}`, {
    method: "GET",
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${await res.text().catch(() => res.statusText)}`);
  }

  const json = (await res.json()) as EmployeesResponse;
  const items = Array.isArray(json?.items) ? (json.items as EmployeeDTO[]) : [];
  const total = Number(json?.total ?? items.length);
  return { items, total };
}

export default function OrgPageClient() {
  const router = useRouter();
  const sp = useSearchParams();

  const apiBase = React.useMemo(() => getApiBase(), []);
  const devUserId = getDevUserId();

  const headers = React.useMemo(() => {
    const h: Record<string, string> = { Accept: "application/json" };
    if (devUserId) h["X-User-Id"] = devUserId;
    return h;
  }, [devUserId]);

  // URL state
  const urlOrgUnitId = React.useMemo(() => parseIntOrNull(sp.get("org_unit_id")), [sp]);
  const urlEmployeeId = React.useMemo(
    () => (sp.get("employee_id") || "").trim() || null,
    [sp]
  );
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
  const [expandedSet, setExpandedSet] = React.useState<Set<number>>(new Set<number>());

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

  // sync expandedSet from URL
  React.useEffect(() => {
    // создаём новый Set чтобы React видел изменение
    setExpandedSet(new Set<number>(Array.from(urlExpanded.values())));
  }, [urlExpanded]);

  // parent map for auto-expansion of selected org_unit
  const parentMap = React.useMemo(() => buildParentMap(orgItems), [orgItems]);

  // 1) load org tree
  React.useEffect(() => {
    let cancelled = false;

    async function loadOrg() {
      setOrgLoading(true);
      setOrgError(null);

      try {
        const res = await fetch(`${apiBase}/directory/org-units/tree`, {
          method: "GET",
          headers,
          cache: "no-store",
        });

        if (!res.ok) {
          const t = await res.text().catch(() => "");
          throw new Error(`HTTP ${res.status}: ${t || res.statusText}`);
        }

        const json = (await res.json()) as OrgTreeResponse;
        const items = Array.isArray(json?.items) ? json.items : [];

        if (cancelled) return;

        setOrgItems(items);

        const flat = flattenUnits(items);

        // priority:
        // 1) org_unit_id from URL
        // 2) first unit
        if (urlOrgUnitId != null) {
          const found = flat.find((u) => u.unit_id === urlOrgUnitId);
          if (found) {
            setSelectedUnit(found);
            // expanded: раскрываем предков выбранного узла (без изменения существующего expanded, если он уже есть)
            // если expanded отсутствует — записываем минимально необходимое
            if (!sp.get("expanded")) {
              const pm = buildParentMap(items);
              const need = new Set<number>();
              ancestorsOf(found.unit_id, pm).forEach((x) => need.add(x));
              need.add(found.unit_id);
              replaceUrl({ expanded: serializeExpanded(need) });
            }
            return;
          }
        }

        if (!selectedUnit && flat.length > 0) {
          const first = flat[0];
          setSelectedUnit(first);

          const next: Partial<Record<string, string | null>> = {};
          if (sp.get("org_unit_id") == null) next.org_unit_id = String(first.unit_id);

          if (sp.get("expanded") == null) {
            const pm = buildParentMap(items);
            const need = new Set<number>();
            ancestorsOf(first.unit_id, pm).forEach((x) => need.add(x));
            need.add(first.unit_id);
            next.expanded = serializeExpanded(need);
          }

          if (Object.keys(next).length > 0) replaceUrl(next);
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
  }, [apiBase, devUserId]);

  // 1b) sync selectedUnit from URL on navigation
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
      if (!selectedUnit) {
        setEmpData({ items: [], total: 0 });
        return;
      }

      setEmpLoading(true);
      setEmpError(null);

      try {
        const data = await fetchEmployeesByOrgUnit({
          apiBase,
          headers,
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
  }, [apiBase, headers, selectedUnit]);

  // Sorted employees within the org unit
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

  // Tree filter (context-preserving)
  const searchActive = Boolean(filterText.trim());
  const treeForRender = React.useMemo(() => {
    if (!searchActive) return orgItems;
    return filterOrgTree(orgItems, filterText);
  }, [orgItems, filterText, searchActive]);

  function isExpanded(unitId: number): boolean {
    // при поиске показываем ветки раскрытыми визуально, не трогая expanded в URL
    if (searchActive) return true;
    return expandedSet.has(unitId);
  }

  function toggleExpanded(unitId: number) {
    const next = new Set<number>(Array.from(expandedSet.values()));
    if (next.has(unitId)) next.delete(unitId);
    else next.add(unitId);

    setExpandedSet(next);
    replaceUrl({ expanded: serializeExpanded(next) });
  }

  function ensureExpandedForSelection(unitId: number) {
    const next = new Set<number>(Array.from(expandedSet.values()));
    ancestorsOf(unitId, parentMap).forEach((x) => next.add(x));
    next.add(unitId);

    setExpandedSet(next);
    replaceUrl({ expanded: serializeExpanded(next) });
  }

  function onSelectUnit(u: UnitPick) {
    setSelectedUnit(u);

    // раскрыть предков выбранного узла и зафиксировать expanded в URL
    ensureExpandedForSelection(u.unit_id);

    // смена подразделения сбрасывает employee_id
    replaceUrl({
      org_unit_id: String(u.unit_id),
      employee_id: null,
    });
  }

  function openEmployeeDrawer(employeeId: string) {
    const id = String(employeeId ?? "").trim();
    if (!id) return;

    setDrawerEmployeeId(id);
    setDrawerOpen(true);

    replaceUrl({
      org_unit_id: selectedUnit ? String(selectedUnit.unit_id) : sp.get("org_unit_id") || null,
      employee_id: id,
    });
  }

  function closeEmployeeDrawer() {
    setDrawerOpen(false);
    setDrawerEmployeeId(null);
    replaceUrl({ employee_id: null });
  }

  async function onTerminate(_details: EmployeeDetails) {
    // пока без бизнес-логики: только закрываем
    closeEmployeeDrawer();
  }

  function renderTree(nodes: OrgTreeNode[], depth: number): React.ReactNode {
    const sorted = [...nodes].sort((a, b) =>
      (a.name || "").localeCompare(b.name || "", "ru")
    );

    return sorted.map((n) => {
      const hasChildren = Array.isArray(n.children) && n.children.length > 0;
      const expanded = hasChildren ? isExpanded(n.unit_id) : false;

      const active = selectedUnit?.unit_id === n.unit_id;

      return (
        <div key={n.unit_id}>
          <div className="flex items-stretch">
            <div
              className="flex items-center"
              style={{ paddingLeft: `${Math.max(0, depth) * 12}px` }}
            >
              {hasChildren ? (
                <button
                  type="button"
                  className="mr-2 w-6 h-6 rounded border border-gray-200 hover:bg-gray-50 text-gray-900"
                  onClick={(ev) => {
                    ev.stopPropagation();
                    toggleExpanded(n.unit_id);
                  }}
                  aria-label={expanded ? "Свернуть" : "Развернуть"}
                  title={expanded ? "Свернуть" : "Развернуть"}
                >
                  <span className="text-xs">{expanded ? "▾" : "▸"}</span>
                </button>
              ) : (
                <div className="mr-2 w-6 h-6" />
              )}
            </div>

            <button
              type="button"
              className={[
                "flex-1 text-left px-3 py-2 rounded border text-sm",
                "text-gray-900",
                active ? "bg-gray-100 border-gray-400" : "bg-white border-gray-200 hover:bg-gray-50",
              ].join(" ")}
              onClick={() => onSelectUnit({ unit_id: n.unit_id, name: n.name })}
              title="Выбрать подразделение"
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
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
      <div className="lg:col-span-5">
        <div className="bg-white rounded border">
          <div className="p-3 border-b">
            <div className="font-semibold text-gray-900">Подразделения</div>
            <div className="mt-2">
              <input
                className="w-full border rounded px-3 py-2 text-sm text-gray-900 placeholder:text-gray-500"
                placeholder="Поиск по подразделениям"
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
              />
            </div>
          </div>

          <div className="p-3">
            {orgError ? (
              <div className="border rounded p-3 text-sm text-red-700">{orgError}</div>
            ) : null}

            {orgLoading ? <div className="text-sm text-gray-700">Загрузка…</div> : null}

            {!orgLoading && !orgError ? (
              <div className="space-y-1 max-h-[70vh] overflow-auto">
                {treeForRender.length > 0 ? (
                  renderTree(treeForRender, 0)
                ) : (
                  <div className="text-sm text-gray-700">Ничего не найдено.</div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="lg:col-span-7">
        <div className="bg-white rounded border">
          <div className="p-3 border-b">
            <div className="font-semibold text-gray-900">
              {selectedUnit ? `Сотрудники — ${selectedUnit.name}` : "Сотрудники"}
            </div>
            <div className="text-xs text-gray-700 mt-1">
              {selectedUnit ? `Фильтр: org_unit_id=${selectedUnit.unit_id}` : null}
              {drawerEmployeeId ? ` · employee_id=${drawerEmployeeId}` : null}
              {!searchActive && expandedSet.size > 0
                ? ` · expanded=${serializeExpanded(expandedSet)}`
                : null}
            </div>
          </div>

          <div className="p-3">
            {empError ? (
              <div className="border rounded p-3 text-sm text-red-700">{empError}</div>
            ) : null}

            {empLoading ? <div className="text-sm text-gray-700">Загрузка…</div> : null}

            {!empLoading && !empError ? (
              <>
                <div className="text-sm text-gray-800 mb-2">Найдено: {empData.total}</div>

                <div className="overflow-auto border rounded">
                  <table className="min-w-full text-sm text-gray-900">
                    <thead className="bg-gray-50 text-gray-900">
                      <tr>
                        <th className="text-left font-semibold p-2 border-b">Таб. №</th>
                        <th className="text-left font-semibold p-2 border-b">ФИО</th>
                        <th className="text-left font-semibold p-2 border-b">Отдел</th>
                        <th className="text-left font-semibold p-2 border-b">Должность</th>
                        <th className="text-left font-semibold p-2 border-b">Ставка</th>
                        <th className="text-left font-semibold p-2 border-b">Статус</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedEmployees.map((e: any) => {
                        const id = String(e?.id ?? "");
                        const isSelected = drawerEmployeeId && id === drawerEmployeeId;

                        return (
                          <tr
                            key={id}
                            className={[
                              "hover:bg-gray-50 cursor-pointer",
                              isSelected ? "bg-gray-50" : "",
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
                            <td className="p-2 border-b whitespace-nowrap">{id}</td>
                            <td className="p-2 border-b">{safeFio(e)}</td>
                            <td className="p-2 border-b">{safeDept(e)}</td>
                            <td className="p-2 border-b">{safePos(e)}</td>
                            <td className="p-2 border-b whitespace-nowrap">{safeRate(e)}</td>
                            <td className="p-2 border-b whitespace-nowrap">{safeStatus(e)}</td>
                          </tr>
                        );
                      })}

                      {sortedEmployees.length === 0 ? (
                        <tr>
                          <td className="p-3 text-gray-700" colSpan={6}>
                            Нет сотрудников в выбранном подразделении.
                          </td>
                        </tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>
              </>
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
