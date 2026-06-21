// FILE: corpsite-ui/app/admin/system/_lib/visibilityTabLogic.ts
import type { AdminUser } from "./adminSystemApi.client";
import type { AccessTargetSearchItem } from "./adminSystemApi.client";

export type VisibilityAssignmentMode = "USER" | "DEPARTMENT" | "POSITION";

export const VISIBILITY_MODE_OPTIONS: { id: VisibilityAssignmentMode; label: string }[] = [
  { id: "USER", label: "Выдать одному сотруднику" },
  { id: "DEPARTMENT", label: "Выдать всему отделению" },
  { id: "POSITION", label: "Выдать должности" },
];

export type OrgUnitOption = {
  unitId: number;
  name: string;
  code?: string | null;
  groupId?: number | null;
  groupName?: string | null;
  depth: number;
};

export type VisibilityUserOption = {
  userId: number;
  fullName: string;
  login: string | null;
  positionName: string | null;
  departmentName: string | null;
  employeeId?: string | null;
};

export type EmployeeLike = {
  id?: string;
  fio?: string | null;
  department?: { name?: string | null } | null;
  position?: { id?: number | null; name?: string | null } | null;
  org_unit?: { name?: string | null } | null;
  user?: { user_id?: number; login?: string | null } | null;
};

export type TreeNodeLike = {
  id?: string;
  unit_id?: number;
  name?: string;
  code?: string | null;
  group_id?: number | null;
  children?: TreeNodeLike[];
};

export function flattenOrgUnitTree(
  nodes: TreeNodeLike[],
  depth = 0,
  groupNames: ReadonlyMap<number, string> = new Map(),
): OrgUnitOption[] {
  const out: OrgUnitOption[] = [];
  for (const node of nodes) {
    const unitId = Number(node.unit_id ?? node.id ?? 0);
    if (!Number.isFinite(unitId) || unitId < 1) continue;
    const groupId =
      node.group_id != null && Number(node.group_id) >= 1 ? Number(node.group_id) : null;
    out.push({
      unitId,
      name: String(node.name || `Отделение #${unitId}`).trim(),
      code: node.code ?? null,
      groupId,
      groupName: groupId != null ? groupNames.get(groupId) ?? null : null,
      depth,
    });
    if (node.children?.length) {
      out.push(...flattenOrgUnitTree(node.children, depth + 1, groupNames));
    }
  }
  return out;
}

export function buildDepartmentUserOptions(
  employees: EmployeeLike[],
  adminUsers: AdminUser[],
  department: OrgUnitOption,
): VisibilityUserOption[] {
  const byUserId = new Map<number, VisibilityUserOption>();

  for (const emp of employees) {
    const uid = Number(emp.user?.user_id ?? 0);
    if (!Number.isFinite(uid) || uid < 1) continue;
    byUserId.set(uid, {
      userId: uid,
      fullName: String(emp.fio || emp.user?.login || `User #${uid}`).trim(),
      login: emp.user?.login ?? null,
      positionName: emp.position?.name ?? null,
      departmentName:
        emp.department?.name ?? emp.org_unit?.name ?? department.name ?? null,
      employeeId: emp.id ?? null,
    });
  }

  for (const user of adminUsers) {
    const uid = Number(user.user_id ?? 0);
    if (!Number.isFinite(uid) || uid < 1) continue;
    if (Number(user.unit_id) !== department.unitId) continue;
    if (byUserId.has(uid)) continue;
    byUserId.set(uid, {
      userId: uid,
      fullName: String(user.full_name || user.login || `User #${uid}`).trim(),
      login: user.login ?? null,
      positionName: null,
      departmentName: department.name,
    });
  }

  return Array.from(byUserId.values()).sort((a, b) =>
    (a.fullName || "").localeCompare(b.fullName || "", "ru"),
  );
}

export function countEmployeesWithoutUserAccount(employees: EmployeeLike[]): number {
  return employees.filter((emp) => {
    const uid = Number(emp.user?.user_id ?? 0);
    return !Number.isFinite(uid) || uid < 1;
  }).length;
}

export function filterUserOptionsByQuery(
  options: VisibilityUserOption[],
  query: string,
): VisibilityUserOption[] {
  const q = query.trim().toLowerCase();
  if (!q) return options;
  return options.filter((item) => {
    const haystack = [
      item.fullName,
      item.login,
      item.positionName,
      item.departmentName,
      String(item.userId),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });
}

export function filterOrgUnitsByQuery(
  options: OrgUnitOption[],
  query: string,
): OrgUnitOption[] {
  const q = query.trim().toLowerCase();
  if (!q) return options;
  return options.filter((item) => {
    const haystack = [item.name, item.code, item.groupName, String(item.unitId)]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });
}

export function extractPositionIdsFromEmployees(employees: EmployeeLike[]): Set<number> {
  const ids = new Set<number>();
  for (const emp of employees) {
    const pid = Number(emp.position?.id ?? 0);
    if (Number.isFinite(pid) && pid >= 1) ids.add(pid);
  }
  return ids;
}

export function filterPositionsByDepartmentContext(
  items: AccessTargetSearchItem[],
  staffedPositionIds: Set<number>,
  departmentSelected: boolean,
): AccessTargetSearchItem[] {
  if (!departmentSelected || staffedPositionIds.size === 0) return items;
  return items.filter((item) => staffedPositionIds.has(Number(item.target_id)));
}

export function formatUserOptionLabel(item: VisibilityUserOption): string {
  const parts = [item.fullName];
  if (item.login) parts.push(`login: ${item.login}`);
  if (item.positionName) parts.push(item.positionName);
  if (item.departmentName) parts.push(item.departmentName);
  return parts.join(" · ");
}

export function formatDepartmentOptionLabel(item: OrgUnitOption): string {
  const parts = [item.name];
  if (item.groupName) parts.push(`группа: ${item.groupName}`);
  if (item.code) parts.push(item.code);
  return parts.join(" · ");
}

export function departmentPrefilterRequired(mode: VisibilityAssignmentMode): boolean {
  return mode === "USER";
}

export function departmentPrefilterOptional(mode: VisibilityAssignmentMode): boolean {
  return mode === "POSITION";
}

export function targetSelectionRequired(mode: VisibilityAssignmentMode): boolean {
  return mode === "USER" || mode === "POSITION";
}

export function canSubmitVisibilityAssignment(args: {
  mode: VisibilityAssignmentMode;
  selectedDepartment: OrgUnitOption | null;
  selectedUser: VisibilityUserOption | null;
  selectedDepartmentTarget: OrgUnitOption | null;
  selectedPosition: AccessTargetSearchItem | null;
}): boolean {
  if (args.mode === "USER") {
    return Boolean(args.selectedDepartment && args.selectedUser);
  }
  if (args.mode === "DEPARTMENT") {
    return Boolean(args.selectedDepartmentTarget);
  }
  return Boolean(args.selectedPosition);
}

export function toAccessTargetFromUser(user: VisibilityUserOption): AccessTargetSearchItem {
  return {
    target_type: "USER",
    target_id: user.userId,
    label: user.fullName,
    subtitle: user.login ?? undefined,
    metadata: {
      login: user.login,
      position_name: user.positionName,
      department_name: user.departmentName,
    },
  };
}

export function toAccessTargetFromDepartment(dept: OrgUnitOption): AccessTargetSearchItem {
  return {
    target_type: "ORG_UNIT",
    target_id: dept.unitId,
    label: dept.name,
    subtitle: dept.groupName ?? dept.code ?? undefined,
    metadata: {
      group_id: dept.groupId,
      group_name: dept.groupName,
    },
  };
}
