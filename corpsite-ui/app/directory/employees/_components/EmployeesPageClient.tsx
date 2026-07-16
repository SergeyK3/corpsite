// FILE: corpsite-ui/app/directory/employees/_components/EmployeesPageClient.tsx
"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import OrgScopeFilter from "@/components/OrgScopeFilter";
import { buildEmployeeCardHref } from "@/lib/employeeCardNav";
import { ORG_GROUP_ID_PARAM, readOrgScopeFromSearchParams } from "@/lib/orgScope";
import EmployeesTable from "./EmployeesTable";
import EmployeeDrawer from "./EmployeeDrawer";
import EmployeeCreateDrawer from "./EmployeeCreateDrawer";
import type { EmployeeCreateFormValues } from "./EmployeeCreateForm";

import {
  getEmployees,
  getPositions,
  getDepartments,
  mapApiErrorToMessage,
  createEmployee,
} from "../_lib/api.client";
import { getOrgUnitsTree, type TreeNode } from "../../org-units/_lib/api.client";
import type {
  EmployeeDTO,
  Position,
  Department,
  EmployeesResponse,
} from "../_lib/types";
import type { EmployeesFilters } from "../_lib/query";

type Dept = Department;
type Pos = Position;

type Props = {
  pageTitle?: string;
  /** Read-only management view: no create/edit/transfer actions. */
  readOnly?: boolean;
  /** Simplified table columns for management-facing «Персонал». */
  managementView?: boolean;
  initialFilters: EmployeesFilters;
  initialDepartments: Dept[];
  initialPositions: Pos[];
  initialEmployees: EmployeesResponse;
  initialError?: string | null;
  refreshResetsOrgUnitFilter?: boolean;
};

const ORG_FILTER_PARAM_KEYS = [
  ORG_GROUP_ID_PARAM,
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

// API /directory/positions отдаёт position_id; UI ожидает id (как в PositionsPageClient).
function positionIdOf(p: { id?: number | null; position_id?: number | null }): number {
  return Number(p.position_id ?? p.id ?? 0);
}

function normalizePosition(p: any): Pos {
  const id = positionIdOf(p);
  return {
    id: Number.isFinite(id) && id > 0 ? id : null,
    name: p?.name ?? null,
  };
}

function toInt(v: string | null, def: number): number {
  const n = Number(String(v ?? "").trim());
  return Number.isFinite(n) && n >= 0 ? Math.floor(n) : def;
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

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function buildDefaultCreateValues(orgUnitId: string): EmployeeCreateFormValues {
  return {
    full_name: "",
    org_unit_id: orgUnitId,
    position_id: "",
    date_from: todayIsoDate(),
    employment_rate: "1",
  };
}

function flattenOrgUnits(nodes: TreeNode[], depth = 0): Array<{ id: number; label: string }> {
  const out: Array<{ id: number; label: string }> = [];
  for (const node of nodes) {
    const unitId = Number(node.unit_id ?? node.id);
    if (Number.isFinite(unitId) && unitId > 0) {
      const name = String(node.name ?? node.name_ru ?? `#${unitId}`).trim();
      out.push({ id: unitId, label: `${"— ".repeat(depth)}${name}` });
    }
    if (Array.isArray(node.children) && node.children.length > 0) {
      out.push(...flattenOrgUnits(node.children, depth + 1));
    }
  }
  return out;
}

export default function EmployeesPageClient(props: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const routeBase = React.useMemo(() => {
    if (pathname?.startsWith("/directory/staff")) return "/directory/staff";
    if (pathname?.startsWith("/directory/personnel")) return "/directory/personnel";
    return "/directory/employees";
  }, [pathname]);

  const readOnly = props.readOnly === true;
  const managementView = props.managementView === true;
  const isStaffRoute = routeBase === "/directory/staff";

  const pageTitle =
    props.pageTitle ??
    (routeBase === "/directory/staff"
      ? "Персонал"
      : routeBase === "/directory/personnel"
        ? "Кадровые процессы"
        : "Сотрудники");

  const orgScope = React.useMemo(() => readOrgScopeFromSearchParams(sp), [sp]);
  const orgGroupId = orgScope.org_group_id;

  const departmentId = sp.get("department_id") ?? "";
  const positionId = sp.get("position_id") ?? "";
  const status = sp.get("status") ?? "all";
  const qText = sp.get("q") ?? "";
  const orgUnitId = sp.get("org_unit_id") ?? "";
  const limitStr = sp.get("limit") ?? "50";
  const offsetStr = sp.get("offset") ?? "0";
  const includeApplicants =
    isStaffRoute && (sp.get("include_applicants") === "1" || sp.get("include_applicants") === "true");
  const deepLinkEmployeeId = (sp.get("employeeId") ?? "").trim();

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
  const [search, setSearch] = React.useState(qText);
  const [error, setError] = React.useState<string | null>(
    props.initialError ? String(props.initialError) : null
  );

  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [drawerEmployeeId, setDrawerEmployeeId] = React.useState<string | null>(null);

  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);
  const [createSaving, setCreateSaving] = React.useState(false);
  const [createError, setCreateError] = React.useState<string | null>(null);
  const [orgUnitOptions, setOrgUnitOptions] = React.useState<Array<{ id: number; label: string }>>([]);
  const [createInitialValues, setCreateInitialValues] = React.useState<EmployeeCreateFormValues>(
    buildDefaultCreateValues(orgUnitId)
  );

  const [employeeRefreshToken, setEmployeeRefreshToken] = React.useState(0);

  const prevOrgUnitRef = React.useRef<string>(orgUnitId);
  const prevOrgGroupRef = React.useRef<number | undefined>(orgGroupId);
  const loadSeqRef = React.useRef(0);

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
    if (prevOrgGroupRef.current !== orgGroupId) {
      prevOrgGroupRef.current = orgGroupId;
      if (departmentId || orgUnitId) {
        updateUrl({ department_id: "", org_unit_id: "" }, { resetOffset: true });
        return;
      }
      if (offsetNum !== 0) setPageOffset(0);
    }
  }, [orgGroupId, offsetNum, departmentId, orgUnitId]);

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
        setPositions(normalizeItems<any>(pObj).map(normalizePosition).filter((p) => p.id != null));
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

  React.useEffect(() => {
    let cancelled = false;

    async function loadOrgUnitsForFilter() {
      try {
        const tree = await getOrgUnitsTree({
          org_group_id: orgGroupId ?? undefined,
        });
        if (cancelled) return;
        setOrgUnitOptions(flattenOrgUnits(tree.items ?? []));
      } catch {
        if (cancelled) return;
        setOrgUnitOptions([]);
      }
    }

    void loadOrgUnitsForFilter();
    return () => {
      cancelled = true;
    };
  }, [orgGroupId]);

  React.useEffect(() => {
    setCreateInitialValues(buildDefaultCreateValues(orgUnitId));
  }, [orgUnitId]);

  const loadItems = React.useCallback(async () => {
    const seq = ++loadSeqRef.current;
    setLoading(true);
    setError(null);

    try {
      const json = await getEmployees({
        status,
        department_id: departmentId || null,
        position_id: positionId || null,
        org_group_id: orgGroupId ?? null,
        org_unit_id: orgUnitId || null,
        include_children: Boolean(orgUnitId),
        include_applicants: includeApplicants,
        q: qText || null,
        limit: String(limitNum),
        offset: String(offsetNum),
      });

      if (seq !== loadSeqRef.current) return;

      setData({
        items: Array.isArray(json?.items) ? (json.items as EmployeeDTO[]) : [],
        total: Number(json?.total ?? 0),
      });
    } catch (e) {
      if (seq !== loadSeqRef.current) return;
      setError(mapApiErrorToMessage(e));
      setData({ items: [], total: 0 });
    } finally {
      if (seq === loadSeqRef.current) setLoading(false);
    }
  }, [status, departmentId, positionId, orgGroupId, orgUnitId, qText, limitNum, offsetNum, includeApplicants]);

  React.useEffect(() => {
    void loadItems();
  }, [loadItems]);

  React.useEffect(() => {
    if (!deepLinkEmployeeId) return;
    if (isStaffRoute) {
      router.push(buildEmployeeCardHref(deepLinkEmployeeId));
      return;
    }
    setDrawerEmployeeId(deepLinkEmployeeId);
    setDrawerOpen(true);
  }, [deepLinkEmployeeId, isStaffRoute, router]);

  function applySearch() {
    updateUrl({ q: search }, { resetOffset: true });
  }

  function handleOpenEmployee(id: string) {
    if (isStaffRoute) {
      router.push(buildEmployeeCardHref(id));
      return;
    }
    setDrawerEmployeeId(id);
    setDrawerOpen(true);
  }

  function handleCloseDrawer() {
    setDrawerOpen(false);
    if (deepLinkEmployeeId) {
      const nextParams = new URLSearchParams(sp.toString());
      nextParams.delete("employeeId");
      const qs = nextParams.toString();
      router.replace(qs ? `${routeBase}?${qs}` : routeBase);
    }
  }

  function handleOpenCreateDrawer() {
    setCreateError(null);
    setCreateInitialValues(buildDefaultCreateValues(orgUnitId));
    setCreateDrawerOpen(true);
  }

  function handleCloseCreateDrawer() {
    if (createSaving) return;
    setCreateDrawerOpen(false);
    setCreateError(null);
  }

  async function handleCreateEmployee(values: EmployeeCreateFormValues) {
    setCreateSaving(true);
    setCreateError(null);

    try {
      await createEmployee({
        full_name: values.full_name.trim(),
        org_unit_id: Number(values.org_unit_id),
        position_id: Number(values.position_id),
        date_from: values.date_from || null,
        employment_rate: values.employment_rate ? Number(values.employment_rate) : 1,
      });

      setCreateDrawerOpen(false);
      await loadItems();
    } catch (e) {
      setCreateError(mapApiErrorToMessage(e));
    } finally {
      setCreateSaving(false);
    }
  }

  const depList = Array.isArray(departments) ? departments : [];
  const posList = Array.isArray(positions) ? positions : [];

  const departmentOptions = React.useMemo(() => {
    if (orgGroupId != null) {
      const seen = new Set<number>();
      return orgUnitOptions.filter((unit) => {
        if (seen.has(unit.id)) return false;
        seen.add(unit.id);
        return true;
      });
    }
    const seen = new Set<number>();
    return depList
      .filter((d) => d.id != null)
      .map((d) => ({ id: Number(d.id), label: String(d.name ?? `#${d.id}`) }))
      .filter((d) => {
        if (seen.has(d.id)) return false;
        seen.add(d.id);
        return true;
      });
  }, [orgGroupId, orgUnitOptions, depList]);

  const departmentFilterValue = orgGroupId != null ? orgUnitId : departmentId;
  const isPersonnelRoute = routeBase === "/directory/personnel";
  const showHrImportCardLink = isPersonnelRoute && !readOnly;

  const pageContent = (
    <>
      <div className="border-b border-zinc-200 dark:border-zinc-800 px-4 py-2.5">
            <div className="flex flex-col gap-2 xl:flex-row xl:items-end">
              <OrgScopeFilter
                basePath={routeBase}
                className="min-w-[240px]"
                resetParamsOnChange={["offset", "department_id", "org_unit_id"]}
              />

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  applySearch();
                }}
                className="flex flex-1 gap-2"
              >
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Поиск по ФИО или табельному номеру"
                  className="h-9 min-w-0 flex-1 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 text-[13px] text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                />
                <button
                  type="submit"
                  className="h-9 shrink-0 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 text-[13px] text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
                >
                  Найти
                </button>
              </form>

              <select
                value={departmentFilterValue}
                onChange={(e) => {
                  const value = e.target.value;
                  if (orgGroupId != null) {
                    updateUrl({ org_unit_id: value, department_id: "" }, { resetOffset: true });
                  } else {
                    updateUrl({ department_id: value, org_unit_id: "" }, { resetOffset: true });
                  }
                }}
                className="h-9 min-w-[220px] rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 text-[13px] text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
              >
                <option value="">Все отделы</option>
                {departmentOptions.map((d) => (
                  <option
                    key={d.id}
                    value={String(d.id)}
                    className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50"
                  >
                    {d.label}
                  </option>
                ))}
              </select>

              <select
                value={positionId}
                onChange={(e) => updateUrl({ position_id: e.target.value }, { resetOffset: true })}
                className="h-9 min-w-[220px] rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 text-[13px] text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
              >
                <option value="">Все должности</option>
                {posList.map((p) => (
                  <option key={p.id} value={String(p.id)} className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                    {p.name ?? `#${p.id}`}
                  </option>
                ))}
              </select>

              <select
                value={status}
                onChange={(e) => updateUrl({ status: e.target.value }, { resetOffset: true })}
                className="h-9 min-w-[160px] rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 text-[13px] text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
              >
                <option value="all" className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                  Все
                </option>
                <option value="active" className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                  Работает
                </option>
                <option value="inactive" className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                  Не работает
                </option>
              </select>

              {isStaffRoute ? (
                <label className="flex h-9 items-center gap-2 rounded-lg border border-zinc-200 bg-zinc-100 px-3 text-[13px] text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
                  <input
                    type="checkbox"
                    checked={includeApplicants}
                    onChange={(e) =>
                      updateUrl(
                        { include_applicants: e.target.checked ? "1" : "" },
                        { resetOffset: true },
                      )
                    }
                    data-testid="staff-include-applicants"
                  />
                  Показывать заявителей
                </label>
              ) : null}

              <button
                type="button"
                onClick={handleRefresh}
                className="h-9 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 text-[13px] text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
              >
                Обновить
              </button>

              {!readOnly ? (
                <button
                  type="button"
                  onClick={handleOpenCreateDrawer}
                  className="h-9 rounded-lg bg-blue-600 px-4 text-[13px] font-medium text-white transition hover:bg-blue-500"
                >
                  Создать
                </button>
              ) : null}
            </div>
          </div>

          <div className="px-4 py-3">
            {!!error && (
              <div className="mb-3 rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
                {error}
              </div>
            )}

            <div className="mb-2 text-xs text-zinc-600 dark:text-zinc-400">
              Всего: {data.total} · Показано: {data.items.length}
            </div>

            <EmployeesTable
              items={data.items}
              total={data.total}
              limit={limitNum}
              offset={offsetNum}
              loading={loading}
              onOpenEmployee={handleOpenEmployee}
              onChangePage={setPageOffset}
              showCard2Button={showHrImportCardLink}
              directPersonalCardNav={isStaffRoute}
              managementView={managementView}
            />
          </div>
    </>
  );

  return (
    <>
      {isPersonnelRoute ? (
        pageContent
      ) : (
        <div className="bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
          <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
            <div className="overflow-hidden rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
              <div className="border-b border-zinc-200 dark:border-zinc-800 px-4 py-3">
                <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{pageTitle}</h1>
              </div>
              {pageContent}
            </div>
          </div>
        </div>
      )}

      {isStaffRoute ? null : (
        <EmployeeDrawer
          employeeId={drawerEmployeeId}
          open={drawerOpen}
          onClose={handleCloseDrawer}
          refreshToken={employeeRefreshToken}
        />
      )}

      {!readOnly ? (
        <EmployeeCreateDrawer
          open={createDrawerOpen}
          initialValues={createInitialValues}
          orgUnitOptions={orgUnitOptions}
          positionOptions={posList.map((p) => ({
            id: Number(p.id),
            label: String(p.name ?? `#${p.id}`),
          })).filter((p) => Number.isFinite(p.id) && p.id > 0)}
          saving={createSaving}
          error={createError}
          onClose={handleCloseCreateDrawer}
          onSubmit={handleCreateEmployee}
        />
      ) : null}
    </>
  );
}