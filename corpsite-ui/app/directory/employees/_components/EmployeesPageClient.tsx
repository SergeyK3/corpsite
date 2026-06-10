// FILE: corpsite-ui/app/directory/employees/_components/EmployeesPageClient.tsx
"use client";

import * as React from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import OrgScopeFilter from "@/components/OrgScopeFilter";
import { ORG_GROUP_ID_PARAM, readOrgScopeFromSearchParams } from "@/lib/orgScope";
import EmployeesTable from "./EmployeesTable";
import EmployeeDrawer from "./EmployeeDrawer";
import EmployeeCreateDrawer from "./EmployeeCreateDrawer";
import UserCreateDrawer from "./UserCreateDrawer";
import type { EmployeeCreateFormValues } from "./EmployeeCreateForm";
import type { UserCreateFormValues } from "./UserCreateForm";

import {
  getEmployees,
  getPositions,
  getDepartments,
  mapApiErrorToMessage,
  terminateEmployee,
  createEmployee,
  createUser,
  getRoles,
} from "../_lib/api.client";
import { getOrgUnitsTree, type TreeNode } from "../../org-units/_lib/api.client";
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

function buildDefaultUserCreateValues(loginSeed = ""): UserCreateFormValues {
  return {
    login: loginSeed,
    password: "",
    role_id: "",
    is_active: true,
  };
}

function translitLoginSeed(name: string): string {
  const map: Record<string, string> = {
    а: "a", б: "b", в: "v", г: "g", д: "d", е: "e", ё: "e", ж: "zh", з: "z", и: "i",
    й: "y", к: "k", л: "l", м: "m", н: "n", о: "o", п: "p", р: "r", с: "s", т: "t",
    у: "u", ф: "f", х: "h", ц: "ts", ч: "ch", ш: "sh", щ: "sch", ъ: "", ы: "y", ь: "",
    э: "e", ю: "yu", я: "ya",
  };
  const parts = String(name || "")
    .trim()
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) return "";
  const last = parts[parts.length - 1] ?? "";
  const firstInitial = (parts[0] ?? "").slice(0, 1);
  const raw = `${last}${firstInitial}`.split("").map((ch) => map[ch] ?? ch).join("");
  return raw.replace(/[^a-z0-9._-]+/g, "").slice(0, 64);
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
    if (pathname?.startsWith("/directory/personnel")) return "/directory/personnel";
    return "/directory/employees";
  }, [pathname]);

  const pageTitle =
    props.pageTitle ?? (routeBase === "/directory/personnel" ? "Персонал" : "Сотрудники");

  const orgScope = React.useMemo(() => readOrgScopeFromSearchParams(sp), [sp]);
  const orgGroupId = orgScope.org_group_id;

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

  const [createDrawerOpen, setCreateDrawerOpen] = React.useState(false);
  const [createSaving, setCreateSaving] = React.useState(false);
  const [createError, setCreateError] = React.useState<string | null>(null);
  const [orgUnitOptions, setOrgUnitOptions] = React.useState<Array<{ id: number; label: string }>>([]);
  const [createInitialValues, setCreateInitialValues] = React.useState<EmployeeCreateFormValues>(
    buildDefaultCreateValues(orgUnitId)
  );

  const [userCreateDrawerOpen, setUserCreateDrawerOpen] = React.useState(false);
  const [userCreateSaving, setUserCreateSaving] = React.useState(false);
  const [userCreateError, setUserCreateError] = React.useState<string | null>(null);
  const [userCreateEmployee, setUserCreateEmployee] = React.useState<EmployeeDetails | null>(null);
  const [userCreateInitialValues, setUserCreateInitialValues] = React.useState<UserCreateFormValues>(
    buildDefaultUserCreateValues()
  );
  const [roleOptions, setRoleOptions] = React.useState<Array<{ id: number; label: string }>>([]);
  const [employeeRefreshToken, setEmployeeRefreshToken] = React.useState(0);

  const prevOrgUnitRef = React.useRef<string>(orgUnitId);
  const prevOrgGroupRef = React.useRef<number | undefined>(orgGroupId);

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
      if (offsetNum !== 0) setPageOffset(0);
    }
  }, [orgGroupId, offsetNum]);

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

  React.useEffect(() => {
    let cancelled = false;

    async function loadOrgUnits() {
      try {
        const tree = await getOrgUnitsTree({
          org_group_id: orgGroupId ?? undefined,
          org_unit_id: orgUnitId || undefined,
        });
        if (cancelled) return;
        setOrgUnitOptions(flattenOrgUnits(tree.items ?? []));
      } catch {
        if (cancelled) return;
        setOrgUnitOptions([]);
      }
    }

    void loadOrgUnits();
    return () => {
      cancelled = true;
    };
  }, [orgGroupId, orgUnitId]);

  React.useEffect(() => {
    setCreateInitialValues(buildDefaultCreateValues(orgUnitId));
  }, [orgUnitId]);

  const loadItems = React.useCallback(async () => {
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
  }, [status, departmentId, positionId, orgGroupId, orgUnitId, qText, limitNum, offsetNum]);

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

  function handleOpenUserCreateDrawer(details: EmployeeDetails) {
    const fio = getEmployeeName(details as any);
    const orgUnitName =
      (details as any)?.org_unit?.name ??
      (details as any)?.orgUnit?.name ??
      (details as any)?.org_unit_name ??
      "—";

    setUserCreateError(null);
    setUserCreateEmployee(details);
    setUserCreateInitialValues(buildDefaultUserCreateValues(translitLoginSeed(fio)));
    setUserCreateDrawerOpen(true);

    void (async () => {
      try {
        const rolesObj = await getRoles({ limit: 200, offset: 0 });
        const items = normalizeItems<any>(rolesObj);
        setRoleOptions(
          items
            .map((r) => ({
              id: Number(r.role_id ?? r.id),
              label: String(r.role_name ?? r.name ?? `#${r.role_id ?? r.id}`),
            }))
            .filter((r) => Number.isFinite(r.id) && r.id > 0)
        );
      } catch {
        setRoleOptions([]);
      }
    })();
  }

  function handleCloseUserCreateDrawer() {
    if (userCreateSaving) return;
    setUserCreateDrawerOpen(false);
    setUserCreateError(null);
    setUserCreateEmployee(null);
  }

  async function handleCreateUser(values: UserCreateFormValues) {
    if (!userCreateEmployee) return;

    const employeeId = Number(getEmployeeId(userCreateEmployee as any));
    if (!Number.isFinite(employeeId) || employeeId < 1) {
      setUserCreateError("Не удалось определить сотрудника.");
      return;
    }

    setUserCreateSaving(true);
    setUserCreateError(null);

    try {
      await createUser({
        employee_id: employeeId,
        role_id: Number(values.role_id),
        login: values.login.trim(),
        password: values.password,
        unit_id: (userCreateEmployee as any)?.org_unit?.unit_id ?? undefined,
        is_active: values.is_active,
      });

      setUserCreateDrawerOpen(false);
      setUserCreateEmployee(null);
      setEmployeeRefreshToken((t) => t + 1);
    } catch (e) {
      setUserCreateError(mapApiErrorToMessage(e));
    } finally {
      setUserCreateSaving(false);
    }
  }

  const userCreateFullName = userCreateEmployee ? getEmployeeName(userCreateEmployee as any) : "";
  const userCreateOrgUnitLabel =
    (userCreateEmployee as any)?.org_unit?.name ??
    (userCreateEmployee as any)?.orgUnit?.name ??
    (userCreateEmployee as any)?.org_unit_name ??
    "—";

  const depList = Array.isArray(departments) ? departments : [];
  const posList = Array.isArray(positions) ? positions : [];

  return (
    <div className="bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
        <div className="overflow-hidden rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
          <div className="border-b border-zinc-200 dark:border-zinc-800 px-4 py-3">
            <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">{pageTitle}</h1>
          </div>

          <div className="border-b border-zinc-200 dark:border-zinc-800 px-4 py-2.5">
            <div className="flex flex-col gap-2 xl:flex-row xl:items-end">
              <OrgScopeFilter
                basePath={routeBase}
                className="min-w-[240px]"
                resetParamsOnChange={["offset"]}
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
                value={departmentId}
                onChange={(e) => updateUrl({ department_id: e.target.value }, { resetOffset: true })}
                className="h-9 min-w-[220px] rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 text-[13px] text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
              >
                <option value="">Все отделы</option>
                {depList.map((d) => (
                  <option key={d.id} value={String(d.id)} className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                    {d.name ?? `#${d.id}`}
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

              <button
                type="button"
                onClick={handleRefresh}
                className="h-9 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 text-[13px] text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
              >
                Обновить
              </button>

              <button
                type="button"
                onClick={handleOpenCreateDrawer}
                className="h-9 rounded-lg bg-blue-600 px-4 text-[13px] font-medium text-white transition hover:bg-blue-500"
              >
                Создать
              </button>
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
        onCreateUser={handleOpenUserCreateDrawer}
        refreshToken={employeeRefreshToken}
      />

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

      <UserCreateDrawer
        open={userCreateDrawerOpen}
        fullName={userCreateFullName}
        orgUnitLabel={userCreateOrgUnitLabel}
        initialValues={userCreateInitialValues}
        roleOptions={roleOptions}
        saving={userCreateSaving}
        error={userCreateError}
        onClose={handleCloseUserCreateDrawer}
        onSubmit={handleCreateUser}
      />
    </div>
  );
}