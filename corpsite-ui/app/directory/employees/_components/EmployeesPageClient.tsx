// FILE: corpsite-ui/app/directory/employees/_components/EmployeesPageClient.tsx
"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import EmployeesTable from "./EmployeesTable";
import EmployeeDrawer from "./EmployeeDrawer";

import {
  getEmployees,
  getPositions,
  getDepartments,
  mapApiErrorToMessage,
  terminateEmployee,
} from "../_lib/api.client";
import type {
  EmployeeDTO,
  Position,
  Department,
  EmployeesResponse,
  EmployeeDetails,
} from "../_lib/types";
import type { EmployeesFilters } from "../_lib/query";

type Dept = Department;
type Pos = Position;

type Props = {
  pageTitle?: string;
  initialFilters: EmployeesFilters;
  initialDepartments: Dept[];
  initialPositions: Pos[];
  initialEmployees: EmployeesResponse;
  initialError?: string | null;
  refreshResetsOrgUnitFilter?: boolean;
};

const ORG_FILTER_PARAM_KEYS = [
  "org_unit_id",
  "unit_id",
  "orgUnitId",
  "selected_org_unit_id",
  "ou",
  "unit",
  "org_unit_name",
] as const;

function normalizeItems<T>(v: any): T[] {
  if (Array.isArray(v)) return v as T[];
  if (v && Array.isArray(v.items)) return v.items as T[];
  return [];
}

function toInt(v: string | null, def: number): number {
  const n = Number(String(v ?? "").trim());
  return Number.isFinite(n) && n >= 0 ? Math.floor(n) : def;
}

function getEmployeeId(it: any): string {
  const v = it?.employee_id ?? it?.employeeId ?? it?.id;
  return v == null ? "" : String(v);
}

function getEmployeeName(it: any): string {
  return String(it?.fio ?? it?.full_name ?? it?.fullName ?? it?.name ?? "—");
}

function buildUrlWithoutOrgFilter(basePath: string, sp: ReturnType<typeof useSearchParams>): string {
  const nextParams = new URLSearchParams(sp.toString());

  for (const key of ORG_FILTER_PARAM_KEYS) {
    nextParams.delete(key);
  }

  nextParams.set("offset", "0");
  if (!nextParams.get("limit")) nextParams.set("limit", "50");
  if (!nextParams.get("status")) nextParams.set("status", "all");

  const query = nextParams.toString();
  return query ? `${basePath}?${query}` : basePath;
}

export default function EmployeesPageClient(props: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const routeBase = React.useMemo(() => {
    if (pathname?.startsWith("/directory/personnel")) return "/directory/personnel";
    return "/directory/employees";
  }, [pathname]);

  const pageTitle =
    props.pageTitle ?? (routeBase === "/directory/personnel" ? "Персонал" : "Сотрудники");

  const departmentId = sp.get("department_id") ?? "";
  const positionId = sp.get("position_id") ?? "";
  const status = sp.get("status") ?? "all";
  const qText = sp.get("q") ?? "";
  const orgUnitId = sp.get("org_unit_id") ?? "";
  const limitStr = sp.get("limit") ?? "50";
  const offsetStr = sp.get("offset") ?? "0";

  const limitNum = React.useMemo(() => Math.max(1, toInt(limitStr, 50)), [limitStr]);
  const offsetNum = React.useMemo(() => Math.max(0, toInt(offsetStr, 0)), [offsetStr]);

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
  const [saving, setSaving] = React.useState(false);
  const [search, setSearch] = React.useState(qText);
  const [error, setError] = React.useState<string | null>(
    props.initialError ? String(props.initialError) : null
  );

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerEmployeeId, setDrawerEmployeeId] = React.useState<string | null>(null);

  const prevOrgUnitRef = React.useRef<string>(orgUnitId);

  function updateUrl(next: Partial<Record<string, string>>, opts?: { resetOffset?: boolean }) {
    const resetOffset = opts?.resetOffset !== false;
    const nextParams = new URLSearchParams(sp.toString());

    Object.entries(next).forEach(([k, v]) => {
      const s = (v ?? "").trim();
      if (!s) nextParams.delete(k);
      else nextParams.set(k, s);
    });

    if (resetOffset) nextParams.set("offset", "0");
    if (!nextParams.get("limit")) nextParams.set("limit", "50");
    if (!nextParams.get("status")) nextParams.set("status", "all");

    router.replace(`${routeBase}?${nextParams.toString()}`);
  }

  function setPageOffset(nextOffset: number) {
    const nextParams = new URLSearchParams(sp.toString());
    nextParams.set("offset", String(Math.max(0, Math.floor(nextOffset))));
    if (!nextParams.get("limit")) nextParams.set("limit", "50");
    if (!nextParams.get("status")) nextParams.set("status", "all");
    router.replace(`${routeBase}?${nextParams.toString()}`);
  }

  function handleRefresh() {
    setError(null);

    if (props.refreshResetsOrgUnitFilter) {
      const currentUrl = sp.toString() ? `${routeBase}?${sp.toString()}` : routeBase;
      const nextUrl = buildUrlWithoutOrgFilter(routeBase, sp);

      if (nextUrl !== currentUrl) {
        router.replace(nextUrl);
        return;
      }
    }

    void loadItems();
  }

  React.useEffect(() => {
    setSearch(qText);
  }, [qText]);

  React.useEffect(() => {
    if (prevOrgUnitRef.current !== orgUnitId) {
      prevOrgUnitRef.current = orgUnitId;
      if (offsetNum !== 0) setPageOffset(0);
    }
  }, [orgUnitId, offsetNum]);

  React.useEffect(() => {
    let cancelled = false;

    async function loadRefs() {
      try {
        const [dObj, pObj] = await Promise.all([
          getDepartments({ limit: 200, offset: 0 }),
          getPositions({ limit: 200, offset: 0 }),
        ]);

        if (cancelled) return;
        setDepartments(normalizeItems<Dept>(dObj));
        setPositions(normalizeItems<Pos>(pObj));
      } catch {
        if (cancelled) return;
        setDepartments([]);
        setPositions([]);
      }
    }

    void loadRefs();
    return () => {
      cancelled = true;
    };
  }, []);

  const loadItems = React.useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const json = await getEmployees({
        status,
        department_id: departmentId || null,
        position_id: positionId || null,
        org_unit_id: orgUnitId || null,
        q: qText || null,
        limit: String(limitNum),
        offset: String(offsetNum),
      });

      setData({
        items: Array.isArray(json?.items) ? (json.items as EmployeeDTO[]) : [],
        total: Number(json?.total ?? 0),
      });
    } catch (e) {
      setError(mapApiErrorToMessage(e));
      setData({ items: [], total: 0 });
    } finally {
      setLoading(false);
    }
  }, [status, departmentId, positionId, orgUnitId, qText, limitNum, offsetNum]);

  React.useEffect(() => {
    void loadItems();
  }, [loadItems]);

  function applySearch() {
    updateUrl({ q: search }, { resetOffset: true });
  }

  function handleOpenEmployee(id: string) {
    setDrawerEmployeeId(id);
    setDrawerOpen(true);
  }

  function handleCloseDrawer() {
    setDrawerOpen(false);
  }

  async function handleTerminateEmployee(employeeId: string, employeeName: string) {
    const ok = window.confirm(`Завершить работу сотрудника «${employeeName}»?`);
    if (!ok) return;

    setSaving(true);
    setError(null);

    try {
      await terminateEmployee(employeeId);
      await loadItems();
    } catch (e) {
      setError(mapApiErrorToMessage(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleTerminateFromDrawer(details: EmployeeDetails) {
    const employeeId = getEmployeeId(details as any);
    const employeeName = getEmployeeName(details as any);
    if (!employeeId) return;
    await handleTerminateEmployee(employeeId, employeeName);
    setDrawerOpen(false);
  }

  const depList = Array.isArray(departments) ? departments : [];
  const posList = Array.isArray(positions) ? positions : [];

  return (
    <div className="bg-[#04070f] text-zinc-100">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
        <div className="overflow-hidden rounded-2xl border border-zinc-800 bg-[#050816]">
          <div className="border-b border-zinc-800 px-4 py-3">
            <h1 className="text-xl font-semibold text-zinc-100">{pageTitle}</h1>
          </div>

          <div className="border-b border-zinc-800 px-4 py-2.5">
            <div className="flex flex-col gap-2 xl:flex-row xl:items-center">
              <div className="flex-1">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") applySearch();
                  }}
                  placeholder="Поиск по ФИО или табельному номеру"
                  className="h-9 w-full rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                />
              </div>

              <select
                value={departmentId}
                onChange={(e) => updateUrl({ department_id: e.target.value }, { resetOffset: true })}
                className="h-9 min-w-[220px] rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-100 outline-none transition focus:border-zinc-600"
              >
                <option value="">Все отделы</option>
                {depList.map((d) => (
                  <option key={d.id} value={String(d.id)} className="bg-zinc-950 text-zinc-100">
                    {d.name ?? `#${d.id}`}
                  </option>
                ))}
              </select>

              <select
                value={positionId}
                onChange={(e) => updateUrl({ position_id: e.target.value }, { resetOffset: true })}
                className="h-9 min-w-[220px] rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-100 outline-none transition focus:border-zinc-600"
              >
                <option value="">Все должности</option>
                {posList.map((p) => (
                  <option key={p.id} value={String(p.id)} className="bg-zinc-950 text-zinc-100">
                    {p.name ?? `#${p.id}`}
                  </option>
                ))}
              </select>

              <select
                value={status}
                onChange={(e) => updateUrl({ status: e.target.value }, { resetOffset: true })}
                className="h-9 min-w-[160px] rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-100 outline-none transition focus:border-zinc-600"
              >
                <option value="all" className="bg-zinc-950 text-zinc-100">
                  Все
                </option>
                <option value="active" className="bg-zinc-950 text-zinc-100">
                  Работает
                </option>
                <option value="inactive" className="bg-zinc-950 text-zinc-100">
                  Не работает
                </option>
              </select>

              <button
                type="button"
                onClick={handleRefresh}
                className="h-9 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 text-[13px] text-zinc-200 transition hover:bg-zinc-900/60"
              >
                Обновить
              </button>

              <button
                type="button"
                disabled
                title="Backend route для создания сотрудника пока не реализован."
                className="h-9 rounded-lg bg-blue-600 px-4 text-[13px] font-medium text-white opacity-60"
              >
                Создать
              </button>
            </div>
          </div>

          <div className="px-4 py-3">
            {!!error && (
              <div className="mb-3 rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
                {error}
              </div>
            )}

            <div className="mb-2 text-xs text-zinc-400">
              Всего: {data.total} · Показано: {data.items.length}
            </div>

            <EmployeesTable
              items={data.items}
              total={data.total}
              limit={limitNum}
              offset={offsetNum}
              loading={loading || saving}
              onOpenEmployee={handleOpenEmployee}
              onTerminateEmployee={handleTerminateEmployee}
              onChangePage={setPageOffset}
            />
          </div>
        </div>
      </div>

      <EmployeeDrawer
        employeeId={drawerEmployeeId}
        open={drawerOpen}
        onClose={handleCloseDrawer}
        onTerminate={handleTerminateFromDrawer}
      />
    </div>
  );
}