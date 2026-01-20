"use client";

import * as React from "react";

import type {
  OrgTreeNode,
  OrgTreeResponse,
  EmployeeDTO,
  EmployeesResponse,
  EmployeeDetails,
} from "../../employees/lib/types";

import EmployeeDrawer from "../../employees/_components/EmployeeDrawer";
import { getEmployee } from "../../employees/_lib/api.client";

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

function byName(a: UnitPick, b: UnitPick) {
  return (a.name || "").localeCompare(b.name || "", "ru");
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

// Зафиксировали: backend реально принимает org_unit_id
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
  const apiBase = React.useMemo(() => getApiBase(), []);
  const devUserId = getDevUserId();

  const headers = React.useMemo(() => {
    const h: Record<string, string> = { Accept: "application/json" };
    if (devUserId) h["X-User-Id"] = devUserId;
    return h;
  }, [devUserId]);

  const [orgLoading, setOrgLoading] = React.useState(false);
  const [orgError, setOrgError] = React.useState<string | null>(null);
  const [orgItems, setOrgItems] = React.useState<OrgTreeNode[]>([]);
  const [filterText, setFilterText] = React.useState("");

  const [selectedUnit, setSelectedUnit] = React.useState<UnitPick | null>(null);

  const [empLoading, setEmpLoading] = React.useState(false);
  const [empError, setEmpError] = React.useState<string | null>(null);
  const [empData, setEmpData] = React.useState<EmployeesResponse>({ items: [], total: 0 });

  // Drawer state
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerEmployeeId, setDrawerEmployeeId] = React.useState<string | null>(null);

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
        if (!selectedUnit && items.length > 0) {
          setSelectedUnit({ unit_id: items[0].unit_id, name: items[0].name });
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

  const flatUnits = React.useMemo(() => flattenUnits(orgItems).sort(byName), [orgItems]);

  const visibleUnits = React.useMemo(() => {
    const t = filterText.trim().toLowerCase();
    if (!t) return flatUnits;
    return flatUnits.filter((u) => (u.name || "").toLowerCase().includes(t));
  }, [flatUnits, filterText]);

  function openEmployeeDrawer(employeeId: string) {
    const id = String(employeeId ?? "").trim();
    if (!id) return;
    setDrawerEmployeeId(id);
    setDrawerOpen(true);
  }

  function closeEmployeeDrawer() {
    setDrawerOpen(false);
  }

  async function onTerminate(details: EmployeeDetails) {
    // пока без бизнес-логики, просто закрываем
    // (в дальнейшем подключим реальный terminate flow)
    setDrawerOpen(false);
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
                {visibleUnits.map((u) => {
                  const active = selectedUnit?.unit_id === u.unit_id;
                  return (
                    <button
                      key={u.unit_id}
                      type="button"
                      className={[
                        "w-full text-left px-3 py-2 rounded border text-sm",
                        "text-gray-900",
                        active
                          ? "bg-gray-100 border-gray-400"
                          : "bg-white border-gray-200 hover:bg-gray-50",
                      ].join(" ")}
                      onClick={() => setSelectedUnit(u)}
                    >
                      {u.name}
                    </button>
                  );
                })}

                {visibleUnits.length === 0 ? (
                  <div className="text-sm text-gray-700">Ничего не найдено.</div>
                ) : null}
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
                      {empData.items.map((e: any) => (
                        <tr
                          key={String(e.id)}
                          className="hover:bg-gray-50 cursor-pointer"
                          role="button"
                          tabIndex={0}
                          onClick={() => openEmployeeDrawer(String(e.id))}
                          onKeyDown={(ev) => {
                            if (ev.key === "Enter" || ev.key === " ") {
                              ev.preventDefault();
                              openEmployeeDrawer(String(e.id));
                            }
                          }}
                          title="Открыть карточку сотрудника"
                        >
                          <td className="p-2 border-b whitespace-nowrap">{String(e.id)}</td>
                          <td className="p-2 border-b">{safeFio(e)}</td>
                          <td className="p-2 border-b">{safeDept(e)}</td>
                          <td className="p-2 border-b">{safePos(e)}</td>
                          <td className="p-2 border-b whitespace-nowrap">{safeRate(e)}</td>
                          <td className="p-2 border-b whitespace-nowrap">{safeStatus(e)}</td>
                        </tr>
                      ))}

                      {empData.items.length === 0 ? (
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
