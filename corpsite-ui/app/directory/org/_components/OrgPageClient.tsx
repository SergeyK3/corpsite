// FILE: corpsite-ui/app/directory/org/_components/OrgPageClient.tsx
"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import type { EmployeeDTO, EmployeeDetails, EmployeesResponse } from "../../employees/_lib/types";

import EmployeeDrawer from "../../employees/_components/EmployeeDrawer";
import { apiFetchJson } from "../../../../lib/api";

type UnitPick = {
  key: string;
  unit_id: number | null;
  name: string;
};

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
  key: string;
  unit_id: number | null;
  name: string;
  children: OrgTreeNode[];
};

type OrgTreeResponse = {
  items: OrgTreeNode[];
  total?: number;
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

function parseIntOrNull(v: string | null): number | null {
  if (!v) return null;
  const n = Number(String(v).trim());
  return Number.isFinite(n) ? n : null;
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

function nodeKey(raw: ApiOrgUnitNode): string {
  const v = raw?.id ?? raw?.code ?? raw?.unit_id ?? raw?.unitId;
  return String(v ?? "").trim() || "unknown";
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
  return { key, unit_id, name: nodeTitle(raw), children };
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
  }));

  const byKey = new Map<string, OrgTreeNode>();
  nodes.forEach((n) => byKey.set(n.key, { key: n.key, unit_id: n.unit_id, name: n.name, children: [] }));

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

async function fetchOrgTree(extraHeaders: Record<string, string>): Promise<OrgTreeResponse> {
  const raw = await apiFetchJson<ApiOrgUnitsTreeResponse>("/directory/org-units/tree", {
    method: "GET",
    headers: extraHeaders,
  });

  const itemsRaw = Array.isArray(raw?.items) ? raw.items : [];
  const looksTree = itemsRaw.some((x) => Array.isArray(x?.children) && (x!.children!.length > 0));
  if (looksTree) return { items: itemsRaw.map(normalizeOrgUnitNodeTree), total: raw?.total };

  const flatHasParents = itemsRaw.some(
    (x) => x?.parentId != null || x?.parent_id != null || x?.parent_unit_id != null || x?.parentUnitId != null
  );
  if (flatHasParents) return { items: buildTreeFromFlat(itemsRaw), total: raw?.total };

  return { items: itemsRaw.map(normalizeOrgUnitNodeTree), total: raw?.total };
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
      include_children: true,
    },
  });

  const items = Array.isArray((json as any)?.items) ? ((json as any).items as EmployeeDTO[]) : [];
  const total = Number((json as any)?.total ?? items.length);
  return { items, total };
}

// UI helpers
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

// Sorting
type RoleRule = { rank: number; keywords: string[] };
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

  const urlOrgUnitId = React.useMemo(() => parseIntOrNull(sp.get("org_unit_id")), [sp]);
  const urlEmployeeId = React.useMemo(() => (sp.get("employee_id") || "").trim() || null, [sp]);

  const [orgItems, setOrgItems] = React.useState<OrgTreeNode[]>([]);
  const [selectedUnit, setSelectedUnit] = React.useState<UnitPick | null>(null);

  const [empLoading, setEmpLoading] = React.useState(false);
  const [empError, setEmpError] = React.useState<string | null>(null);
  const [empData, setEmpData] = React.useState<EmployeesResponse>({ items: [], total: 0 });

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

  // load org tree only to map org_unit_id -> name and to set default org_unit_id
  React.useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const data = await fetchOrgTree(extraHeaders);
        if (cancelled) return;

        const items = Array.isArray(data?.items) ? data.items : [];
        setOrgItems(items);

        const flat = flattenUnits(items);

        if (urlOrgUnitId != null) {
          const found = flat.find((u) => u.unit_id === urlOrgUnitId);
          if (found) {
            setSelectedUnit(found);
            return;
          }
        }

        // default: first node with numeric unit_id
        const firstSelectable = flat.find((u) => typeof u.unit_id === "number" && u.unit_id != null);
        if (firstSelectable) {
          setSelectedUnit(firstSelectable);
          if (sp.get("org_unit_id") == null) replaceUrl({ org_unit_id: String(firstSelectable.unit_id) });
        }
      } catch {
        if (cancelled) return;
        setOrgItems([]);
        setSelectedUnit(null);
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extraHeaders, devUserId]);

  // sync selected from URL
  React.useEffect(() => {
    if (orgItems.length === 0) return;
    if (urlOrgUnitId == null) return;

    const flat = flattenUnits(orgItems);
    const found = flat.find((u) => u.unit_id === urlOrgUnitId);
    if (!found) return;

    if (selectedUnit?.unit_id !== found.unit_id) setSelectedUnit(found);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlOrgUnitId, orgItems]);

  // load employees
  React.useEffect(() => {
    let cancelled = false;

    (async () => {
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
    })();

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

  function openEmployeeDrawer(employeeId: string) {
    const id = String(employeeId ?? "").trim();
    if (!id) return;
    setDrawerEmployeeId(id);
    setDrawerOpen(true);
    replaceUrl({ employee_id: id });
  }

  function closeEmployeeDrawer() {
    setDrawerOpen(false);
    setDrawerEmployeeId(null);
    replaceUrl({ employee_id: null });
  }

  async function onTerminate(_details: EmployeeDetails) {
    closeEmployeeDrawer();
  }

  return (
    <div className="w-full rounded-2xl border border-zinc-200 bg-zinc-100">
      <div className="border-b border-zinc-200 p-4">
        <div className="text-sm font-semibold text-zinc-900">{selectedUnit ? selectedUnit.name : "Сотрудники"}</div>
        <div className="mt-1 text-xs text-zinc-600">
          {!selectedUnit
            ? "Выберите подразделение слева."
            : selectedUnit.unit_id == null
              ? "Выберите дочернее подразделение."
              : `Сотрудников: ${empData.total}`}
        </div>
      </div>

      <div className="p-4">
        {empError ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{empError}</div>
        ) : null}

        {empLoading ? <div className="text-sm text-zinc-600">Загрузка…</div> : null}

        {!empLoading && !empError ? (
          <div className="overflow-auto rounded-xl border border-zinc-200">
            <table className="min-w-full text-sm text-zinc-900">
              <thead className="bg-zinc-100 text-xs text-zinc-600">
                <tr>
                  <th className="border-b border-zinc-200 p-2 text-left font-semibold">Таб. №</th>
                  <th className="border-b border-zinc-200 p-2 text-left font-semibold">ФИО</th>
                  <th className="border-b border-zinc-200 p-2 text-left font-semibold">Подразделение</th>
                  <th className="border-b border-zinc-200 p-2 text-left font-semibold">Должность</th>
                  <th className="border-b border-zinc-200 p-2 text-left font-semibold">Ставка</th>
                  <th className="border-b border-zinc-200 p-2 text-left font-semibold">Статус</th>
                </tr>
              </thead>
              <tbody>
                {sortedEmployees.map((e: any) => {
                  const id = String(e?.id ?? "");
                  const isSelected = drawerEmployeeId && id === drawerEmployeeId;

                  return (
                    <tr
                      key={id || `${safeFio(e)}-${safePos(e)}-${safeDept(e)}`}
                      className={["cursor-pointer hover:bg-zinc-200", isSelected ? "bg-zinc-200" : ""].join(" ")}
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
                      <td className="border-b border-zinc-200 p-2 whitespace-nowrap">{id}</td>
                      <td className="border-b border-zinc-200 p-2">{safeFio(e)}</td>
                      <td className="border-b border-zinc-200 p-2">{safeDept(e)}</td>
                      <td className="border-b border-zinc-200 p-2">{safePos(e)}</td>
                      <td className="border-b border-zinc-200 p-2 whitespace-nowrap">{safeRate(e)}</td>
                      <td className="border-b border-zinc-200 p-2 whitespace-nowrap">{safeActive(e)}</td>
                    </tr>
                  );
                })}

                {sortedEmployees.length === 0 ? (
                  <tr>
                    <td className="p-3 text-zinc-600" colSpan={6}>
                      Нет сотрудников в выбранном подразделении.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        ) : null}
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