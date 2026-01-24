// corpsite-ui/app/directory/employees/_components/EmployeesPageClient.tsx

"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import EmployeesTable from "./EmployeesTable";
import EmployeeDrawer from "./EmployeeDrawer";

import { getEmployees, getPositions, mapApiErrorToMessage } from "../_lib/api.client";
import type { EmployeeDTO, Position, Department, EmployeesResponse, EmployeeDetails } from "../_lib/types";
import type { EmployeesFilters } from "../_lib/query";

type Dept = Department;
type Pos = Position;

type Props = {
  initialFilters: EmployeesFilters;
  initialDepartments: Dept[];
  initialPositions: Pos[];
  initialEmployees: EmployeesResponse;
  initialError?: string | null;
};

function getApiBase(): string {
  const v = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim().replace(/\/+$/, "");
  return v || "http://127.0.0.1:8000";
}

function getDevUserId(): string | null {
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v ? v : null;
}

function normalizeItems<T>(v: any): T[] {
  if (Array.isArray(v)) return v as T[];
  if (v && Array.isArray(v.items)) return v.items as T[];
  return [];
}

function toInt(v: string | null, def: number): number {
  const n = Number(String(v ?? "").trim());
  return Number.isFinite(n) && n >= 0 ? Math.floor(n) : def;
}

export default function EmployeesPageClient(props: Props) {
  const router = useRouter();
  const sp = useSearchParams();

  const departmentId = sp.get("department_id") ?? "";
  const positionId = sp.get("position_id") ?? "";
  const status = sp.get("status") ?? "all";
  const qText = sp.get("q") ?? "";

  const limitStr = sp.get("limit") ?? "50";
  const offsetStr = sp.get("offset") ?? "0";

  const limitNum = React.useMemo(() => Math.max(1, toInt(limitStr, 50)), [limitStr]);
  const offsetNum = React.useMemo(() => Math.max(0, toInt(offsetStr, 0)), [offsetStr]);

  const apiBase = React.useMemo(() => getApiBase(), []);
  const devUserId = getDevUserId();

  const [departments, setDepartments] = React.useState<Dept[]>(
    Array.isArray(props.initialDepartments) ? props.initialDepartments : []
  );
  const [positions, setPositions] = React.useState<Pos[]>(
    Array.isArray(props.initialPositions) ? props.initialPositions : []
  );

  const [data, setData] = React.useState<EmployeesResponse>(
    props.initialEmployees && Array.isArray(props.initialEmployees.items)
      ? props.initialEmployees
      : { items: [], total: 0 }
  );
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(props.initialError ? String(props.initialError) : null);

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerEmployeeId, setDrawerEmployeeId] = React.useState<string | null>(null);

  // обновление URL; по умолчанию сбрасываем offset на 0 (для фильтров/поиска)
  function updateUrl(next: Partial<Record<string, string>>, opts?: { resetOffset?: boolean }) {
    const resetOffset = opts?.resetOffset !== false; // default true
    const nextParams = new URLSearchParams(sp.toString());

    Object.entries(next).forEach(([k, v]) => {
      const s = (v ?? "").trim();
      if (!s) nextParams.delete(k);
      else nextParams.set(k, s);
    });

    if (resetOffset) nextParams.set("offset", "0");

    if (!nextParams.get("limit")) nextParams.set("limit", "50");
    if (!nextParams.get("status")) nextParams.set("status", "all");

    router.replace(`/directory/employees?${nextParams.toString()}`);
  }

  function setPageOffset(nextOffset: number) {
    const nextParams = new URLSearchParams(sp.toString());
    nextParams.set("offset", String(Math.max(0, Math.floor(nextOffset))));
    if (!nextParams.get("limit")) nextParams.set("limit", "50");
    if (!nextParams.get("status")) nextParams.set("status", "all");
    router.replace(`/directory/employees?${nextParams.toString()}`);
  }

  // 1) справочники
  React.useEffect(() => {
    let cancelled = false;

    async function loadRefs() {
      try {
        const headers: Record<string, string> = { Accept: "application/json" };
        if (devUserId) headers["X-User-Id"] = devUserId;

        const [dRes, pObj] = await Promise.all([
          fetch(`${apiBase}/directory/departments`, { headers, cache: "no-store" }),
          getPositions({ limit: 200, offset: 0 }),
        ]);

        const dJson = await dRes.json().catch(() => ({} as any));
        const deps = normalizeItems<Dept>(dJson);
        const pos = normalizeItems<Pos>(pObj);

        if (cancelled) return;

        setDepartments(deps);
        setPositions(pos);
      } catch {
        if (cancelled) return;
        // справочники не критичны
        setDepartments([]);
        setPositions([]);
      }
    }

    loadRefs();
    return () => {
      cancelled = true;
    };
  }, [apiBase, devUserId]);

  // 2) список сотрудников
  React.useEffect(() => {
    let cancelled = false;

    async function loadEmployees() {
      setLoading(true);
      setError(null);

      try {
        const json = await getEmployees({
          status,
          department_id: departmentId || null,
          position_id: positionId || null,
          q: qText || null,
          limit: String(limitNum),
          offset: String(offsetNum),
        });

        if (cancelled) return;

        setData({
          items: Array.isArray(json?.items) ? (json.items as EmployeeDTO[]) : [],
          total: Number(json?.total ?? 0),
        });
      } catch (e) {
        if (cancelled) return;
        setError(mapApiErrorToMessage(e));
        setData({ items: [], total: 0 });
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadEmployees();
    return () => {
      cancelled = true;
    };
  }, [departmentId, positionId, status, qText, limitNum, offsetNum]);

  function onRowClick(id: string) {
    setDrawerEmployeeId(id);
    setDrawerOpen(true);
  }

  function onCloseDrawer() {
    setDrawerOpen(false);
  }

  function onTerminate(_details: EmployeeDetails) {
    setDrawerOpen(false);
  }

  const depList = Array.isArray(departments) ? departments : [];
  const posList = Array.isArray(positions) ? positions : [];

  return (
    <div className="space-y-4">
      <div className="bg-white rounded border p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <div className="text-xs text-gray-700 mb-1">Поиск</div>
            <input
              className="w-full border rounded px-3 py-2 text-sm text-gray-900 placeholder:text-gray-500"
              placeholder="ФИО или таб. №"
              value={qText}
              onChange={(e) => updateUrl({ q: e.target.value }, { resetOffset: true })}
            />
          </div>

          <div>
            <div className="text-xs text-gray-700 mb-1">Отдел</div>
            <select
              className="w-full border rounded px-3 py-2 text-sm text-gray-900"
              value={departmentId}
              onChange={(e) => updateUrl({ department_id: e.target.value }, { resetOffset: true })}
            >
              <option value="">Все</option>
              {depList.map((d) => (
                <option key={d.id} value={String(d.id)}>
                  {d.name ?? `#${d.id}`}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div className="text-xs text-gray-700 mb-1">Должность</div>
            <select
              className="w-full border rounded px-3 py-2 text-sm text-gray-900"
              value={positionId}
              onChange={(e) => updateUrl({ position_id: e.target.value }, { resetOffset: true })}
            >
              <option value="">Все</option>
              {posList.map((p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.name ?? `#${p.id}`}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div className="text-xs text-gray-700 mb-1">Статус</div>
            <select
              className="w-full border rounded px-3 py-2 text-sm text-gray-900"
              value={status}
              onChange={(e) => updateUrl({ status: e.target.value }, { resetOffset: true })}
            >
              <option value="all">Все</option>
              <option value="active">Работает</option>
              <option value="inactive">Не работает</option>
            </select>
          </div>
        </div>
      </div>

      {error ? (
        <div className="bg-white rounded border p-4 text-red-700 text-sm">Ошибка загрузки: {error}</div>
      ) : null}

      <EmployeesTable
        items={data.items}
        total={data.total}
        limit={limitNum}
        offset={offsetNum}
        loading={loading}
        onOpenEmployee={onRowClick}
        onChangePage={setPageOffset}
      />

      <EmployeeDrawer employeeId={drawerEmployeeId} open={drawerOpen} onClose={onCloseDrawer} onTerminate={onTerminate} />
    </div>
  );
}
