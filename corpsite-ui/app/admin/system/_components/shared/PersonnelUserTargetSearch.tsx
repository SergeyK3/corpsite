"use client";

import { useEffect, useMemo, useState } from "react";

import { getEmployees, getPositions } from "@/app/directory/employees/_lib/api.client";
import { getOrgUnitsTree } from "@/app/directory/org-units/_lib/api.client";
import { apiFetchJson } from "@/lib/api";

import { fetchAdminUsers, type AccessTargetSearchItem, type AdminUser } from "../../_lib/adminSystemApi.client";
import { flattenOrgUnitTree, formatDepartmentOptionLabel, sortDepartmentGroupOptions, type DepartmentGroupOption, type OrgUnitOption } from "../../_lib/visibilityTabLogic";

type Props = { value: AccessTargetSearchItem | null; onChange: (item: AccessTargetSearchItem | null) => void };
type PositionOption = { id: number; name: string };

function positionsFrom(payload: unknown): PositionOption[] {
  const rows = Array.isArray(payload) ? payload : payload && typeof payload === "object" && Array.isArray((payload as { items?: unknown[] }).items) ? (payload as { items: unknown[] }).items : [];
  return rows.flatMap((row) => {
    const item = row as { position_id?: unknown; id?: unknown; name?: unknown };
    const id = Number(item.position_id ?? item.id);
    const name = String(item.name ?? "").trim();
    return Number.isFinite(id) && id > 0 && name ? [{ id, name }] : [];
  });
}

function targetFrom(employee: { fio?: string | null; department?: { name?: string | null } | null; org_unit?: { name?: string | null } | null; position?: { name?: string | null } | null; user?: { user_id?: number; login?: string | null } | null }): AccessTargetSearchItem | null {
  const userId = Number(employee.user?.user_id ?? 0);
  if (!Number.isFinite(userId) || userId < 1) return null;
  const name = String(employee.fio ?? employee.user?.login ?? "").trim();
  const login = String(employee.user?.login ?? "").trim();
  const department = String(employee.department?.name ?? employee.org_unit?.name ?? "").trim();
  const position = String(employee.position?.name ?? "").trim();
  return { target_type: "USER", target_id: userId, label: name || login || "Пользователь", subtitle: [login ? `login: ${login}` : null, position, department].filter(Boolean).join(" · "), metadata: { login: login || null, position_name: position || null, department_name: department || null } };
}

function targetFromTechnicalUser(user: AdminUser): AccessTargetSearchItem | null {
  const userId = Number(user.user_id);
  const login = String(user.login ?? "").trim();
  if (!Number.isFinite(userId) || userId < 1 || !login) return null;
  const role = String(user.role_name ?? "").trim();
  return {
    target_type: "USER",
    target_id: userId,
    label: login,
    subtitle: role ? `Системная роль: ${role}` : "Техническая учётная запись",
    metadata: { login, role_name: role || null, technical: true },
  };
}

function userMatchesQuery(user: AdminUser, query: string): boolean {
  const q = query.trim().toLocaleLowerCase();
  if (!q) return true;
  return [user.login, user.full_name].some((value) => String(value ?? "").toLocaleLowerCase().includes(q));
}

async function fetchAllAdminUsers(): Promise<AdminUser[]> {
  const limit = 500;
  const users: AdminUser[] = [];
  for (let offset = 0; ; offset += limit) {
    const page = await fetchAdminUsers({ limit, offset });
    users.push(...page);
    if (page.length < limit) return users;
  }
}

/** Personnel filters only find existing linked USER records; they never provision accounts. */
export default function PersonnelUserTargetSearch({ value, onChange }: Props) {
  const [groups, setGroups] = useState<DepartmentGroupOption[]>([]);
  const [departments, setDepartments] = useState<OrgUnitOption[]>([]);
  const [positions, setPositions] = useState<PositionOption[]>([]);
  const [groupId, setGroupId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [positionId, setPositionId] = useState("");
  const [fioQuery, setFioQuery] = useState("");
  const [results, setResults] = useState<AccessTargetSearchItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => { void (async () => {
    try {
      const [tree, groupsBody, positionsBody] = await Promise.all([
        getOrgUnitsTree({ include_inactive: false }),
        apiFetchJson<{ items?: { group_id: number; group_name?: string }[] }>("/directory/department-groups"),
        getPositions({ limit: 1000, offset: 0 }),
      ]);
      const groupRows = (groupsBody.items ?? []).flatMap((group) => {
        const id = Number(group.group_id);
        return Number.isFinite(id) && id > 0 ? [{ groupId: id, groupName: String(group.group_name || `Группа #${id}`).trim() }] : [];
      });
      const names = new Map(groupRows.map((group) => [group.groupId, group.groupName]));
      setGroups(sortDepartmentGroupOptions(groupRows));
      setDepartments(flattenOrgUnitTree(tree.items, 0, names));
      setPositions(positionsFrom(positionsBody));
    } catch { setGroups([]); setDepartments([]); setPositions([]); }
  })(); }, []);

  const visibleDepartments = useMemo(() => {
    const id = Number(groupId);
    return Number.isFinite(id) && id > 0 ? departments.filter((department) => department.groupId === id) : departments;
  }, [departments, groupId]);

  useEffect(() => {
    if (departmentId && !visibleDepartments.some((department) => department.unitId === Number(departmentId))) setDepartmentId("");
  }, [departmentId, visibleDepartments]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void (async () => {
      setLoading(true);
      try {
        const [response, users] = await Promise.all([
          getEmployees({ status: "active", org_group_id: groupId || null, org_unit_id: departmentId || null, position_id: positionId || null, q: fioQuery || null, limit: 50 }),
          fetchAllAdminUsers(),
        ]);
        const byUserId = new Map<number, AccessTargetSearchItem>();
        for (const employee of response.items) { const item = targetFrom(employee); if (item) byUserId.set(item.target_id, item); }
        const hasPersonnelFilter = Boolean(groupId || departmentId || positionId);
        for (const user of users) {
          if (user.is_active === false || !userMatchesQuery(user, fioQuery)) continue;
          // Personnel filters apply only to linked employee records.
          if (user.employee_id == null) {
            const item = targetFromTechnicalUser(user);
            if (item) byUserId.set(item.target_id, item);
          } else if (!hasPersonnelFilter && !byUserId.has(user.user_id)) {
            // The personnel endpoint searches FIO; the catalogue also makes login
            // searches for linked accounts work.
            const item = targetFromTechnicalUser(user);
            if (item) byUserId.set(item.target_id, item);
          }
        }
        setResults(Array.from(byUserId.values()));
      } catch { setResults([]); } finally { setLoading(false); }
    })(); }, 250);
    return () => window.clearTimeout(timer);
  }, [departmentId, fioQuery, groupId, positionId]);

  return <div className="space-y-3 text-sm" data-testid="personnel-user-target-search">
    <div className="grid gap-3 sm:grid-cols-3">
      <label><span className="mb-1 block font-medium">Группа отделений</span><select aria-label="Группа отделений" value={groupId} onChange={(event) => setGroupId(event.target.value)} className="w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"><option value="">Все группы</option>{groups.map((group) => <option key={group.groupId} value={group.groupId}>{group.groupName}</option>)}</select></label>
      <label><span className="mb-1 block font-medium">Отделение</span><select aria-label="Отделение" value={departmentId} onChange={(event) => setDepartmentId(event.target.value)} className="w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"><option value="">Все отделения</option>{visibleDepartments.map((department) => <option key={department.unitId} value={department.unitId}>{formatDepartmentOptionLabel(department)}</option>)}</select></label>
      <label><span className="mb-1 block font-medium">Должность</span><select aria-label="Должность" value={positionId} onChange={(event) => setPositionId(event.target.value)} className="w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"><option value="">Все должности</option>{positions.map((position) => <option key={position.id} value={position.id}>{position.name}</option>)}</select></label>
    </div>
    {value ? <div className="flex items-center justify-between rounded border border-green-300 bg-green-50 px-2 py-1 dark:border-green-800 dark:bg-green-950/30"><span>{value.label}{value.subtitle ? ` — ${value.subtitle}` : ""}</span><button type="button" className="text-xs underline" onClick={() => onChange(null)}>Сменить</button></div> : <>
      <label><span className="mb-1 block font-medium">Поиск по ФИО</span><input aria-label="Поиск по ФИО" type="search" value={fioQuery} onChange={(event) => setFioQuery(event.target.value)} placeholder="ФИО сотрудника" className="w-full rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900" /></label>
      {loading ? <p className="text-xs text-zinc-500">Поиск…</p> : null}
      {!loading && results.length > 0 ? <ul className="max-h-52 overflow-auto rounded border dark:border-zinc-700">{results.map((item) => <li key={item.target_id}><button type="button" className="block w-full px-2 py-1.5 text-left text-xs hover:bg-zinc-100 dark:hover:bg-zinc-800" onClick={() => onChange(item)}><div className="font-medium">{item.label}</div><div className="text-zinc-500">{item.subtitle}</div></button></li>)}</ul> : null}
      {!loading && results.length === 0 ? <p className="text-xs text-zinc-500">Пользователи не найдены.</p> : null}
    </>}
  </div>;
}
