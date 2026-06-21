// FILE: corpsite-ui/app/admin/system/_lib/visibilityTabLogic.ts
import type { AdminUser, PersonnelVisibilityCreate } from "./adminSystemApi.client";
import type { AccessTargetSearchItem } from "./adminSystemApi.client";

export type VisibilityAssignmentMode = "USER" | "DEPARTMENT" | "POSITION";

export const VISIBILITY_MODE_OPTIONS: { id: VisibilityAssignmentMode; label: string }[] = [
  { id: "USER", label: "Выдать одному сотруднику" },
  { id: "DEPARTMENT", label: "Выдать всему отделению" },
  { id: "POSITION", label: "Выдать должности" },
];

export type DepartmentGroupOption = {
  groupId: number;
  groupName: string;
};

const DEPARTMENT_GROUP_ORDER = [
  "Клинические",
  "Параклинические",
  "Административно-хозяйственные",
];

export function sortDepartmentGroupOptions(
  groups: DepartmentGroupOption[],
): DepartmentGroupOption[] {
  return [...groups].sort((a, b) => {
    const ai = DEPARTMENT_GROUP_ORDER.indexOf(a.groupName);
    const bi = DEPARTMENT_GROUP_ORDER.indexOf(b.groupName);
    if (ai !== -1 || bi !== -1) {
      return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    }
    return a.groupName.localeCompare(b.groupName, "ru");
  });
}

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

export function parseDepartmentGroupFilterValue(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const gid = Number(trimmed);
  return Number.isFinite(gid) && gid >= 1 ? gid : null;
}

export function filterOrgUnitsByGroup(
  options: OrgUnitOption[],
  groupId: number | null | undefined,
): OrgUnitOption[] {
  if (groupId == null || groupId < 1) return options;
  return options.filter((item) => item.groupId === groupId);
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

export function filterOrgUnitsByGroupAndQuery(
  options: OrgUnitOption[],
  groupId: number | null | undefined,
  query: string,
): OrgUnitOption[] {
  return filterOrgUnitsByQuery(filterOrgUnitsByGroup(options, groupId), query);
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
  selectedDepartmentTargetIds: ReadonlySet<number>;
  selectedPosition: AccessTargetSearchItem | null;
}): boolean {
  if (args.mode === "USER") {
    return Boolean(args.selectedDepartment && args.selectedUser);
  }
  if (args.mode === "DEPARTMENT") {
    return args.selectedDepartmentTargetIds.size > 0;
  }
  return Boolean(args.selectedPosition);
}

export function toggleDepartmentTargetSelection(
  selectedIds: ReadonlySet<number>,
  unitId: number,
): Set<number> {
  const next = new Set(selectedIds);
  if (next.has(unitId)) next.delete(unitId);
  else next.add(unitId);
  return next;
}

export function selectAllVisibleDepartmentTargets(
  selectedIds: ReadonlySet<number>,
  visibleDepartments: OrgUnitOption[],
): Set<number> {
  const next = new Set(selectedIds);
  for (const dept of visibleDepartments) {
    next.add(dept.unitId);
  }
  return next;
}

export function clearDepartmentTargetSelection(): Set<number> {
  return new Set();
}

export function pruneDepartmentTargetSelectionByGroup(
  selectedIds: ReadonlySet<number>,
  groupId: number | null | undefined,
  departmentsById: ReadonlyMap<number, OrgUnitOption>,
): Set<number> {
  if (groupId == null || groupId < 1) return new Set(selectedIds);
  const next = new Set<number>();
  for (const id of selectedIds) {
    const dept = departmentsById.get(id);
    if (dept?.groupId === groupId) next.add(id);
  }
  return next;
}

export type BulkDepartmentVisibilityPayload = {
  departmentId: number;
  payload: PersonnelVisibilityCreate;
};

export function buildBulkDepartmentVisibilityPayloads(args: {
  departmentIds: Iterable<number>;
  scopeType: string;
  scopeDepartmentId: number | null;
  scopeDepartmentGroupId: number | null;
  canViewTasks: boolean;
}): BulkDepartmentVisibilityPayload[] {
  return Array.from(args.departmentIds)
    .filter((id) => Number.isFinite(id) && id >= 1)
    .sort((a, b) => a - b)
    .map((departmentId) => ({
      departmentId,
      payload: {
        target_type: "DEPARTMENT",
        target_user_id: null,
        target_position_id: null,
        target_department_id: departmentId,
        scope_type: args.scopeType,
        scope_department_id: args.scopeDepartmentId,
        scope_department_group_id: args.scopeDepartmentGroupId,
        can_view_personnel: true,
        can_view_tasks: args.canViewTasks,
      },
    }));
}

export type BulkVisibilityCreateOutcome = "success" | "duplicate" | "failed";

export type BulkVisibilityCreateItemResult = {
  departmentId: number;
  outcome: BulkVisibilityCreateOutcome;
  errorMessage?: string;
};

export type BulkVisibilityCreateSummary = {
  successCount: number;
  duplicateCount: number;
  failedCount: number;
  message: string;
};

export function classifyBulkVisibilityCreateError(err: unknown): BulkVisibilityCreateOutcome {
  const status = Number((err as { status?: number })?.status ?? 0);
  if (status === 409) return "duplicate";

  const parts: string[] = [];
  if (err instanceof Error && err.message.trim()) parts.push(err.message.trim());
  const detail = (err as { detail?: unknown })?.detail;
  if (typeof detail === "string" && detail.trim()) parts.push(detail.trim());
  const msg = parts.join(" ").toLowerCase();

  if (
    msg.includes("already exists") ||
    msg.includes("уже существует") ||
    msg.includes("duplicate") ||
    msg.includes("conflict")
  ) {
    return "duplicate";
  }
  return "failed";
}

export function summarizeBulkVisibilityCreateResults(
  results: BulkVisibilityCreateItemResult[],
): BulkVisibilityCreateSummary {
  const successCount = results.filter((r) => r.outcome === "success").length;
  const duplicateCount = results.filter((r) => r.outcome === "duplicate").length;
  const failedCount = results.filter((r) => r.outcome === "failed").length;

  const parts: string[] = [];
  if (successCount > 0) parts.push(`создано: ${successCount}`);
  if (duplicateCount > 0) parts.push(`уже существует: ${duplicateCount}`);
  if (failedCount > 0) parts.push(`ошибок: ${failedCount}`);

  const failedSamples = results
    .filter((r) => r.outcome === "failed" && r.errorMessage)
    .slice(0, 3)
    .map((r) => `#${r.departmentId}: ${r.errorMessage}`);

  let message = parts.length > 0 ? parts.join("; ") : "Нет результатов";
  if (failedSamples.length > 0) {
    message = `${message}. ${failedSamples.join("; ")}`;
  }

  return { successCount, duplicateCount, failedCount, message };
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

export type VisibilityAssignmentRowLike = {
  target_type: string;
  target_user_id?: number | null;
  target_position_id?: number | null;
  target_department_id?: number | null;
};

export type VisibilityAssignmentRecordLike = VisibilityAssignmentRowLike & {
  assignment_id?: number;
  scope_type: string;
  scope_department_id?: number | null;
  scope_department_group_id?: number | null;
  can_view_tasks?: boolean;
  is_active?: boolean;
};

export type VisibilityAssignmentSummary = {
  activeCount: number;
  revokedCount: number;
  userCount: number;
  positionCount: number;
  departmentCount: number;
  duplicateGroupCount: number;
};

export function visibilityAssignmentDedupeKey(row: VisibilityAssignmentRecordLike): string {
  const targetType = String(row.target_type ?? "").trim().toUpperCase();
  let targetId = "?";
  if (targetType === "USER") targetId = String(row.target_user_id ?? "?");
  else if (targetType === "POSITION") targetId = String(row.target_position_id ?? "?");
  else if (targetType === "DEPARTMENT") targetId = String(row.target_department_id ?? "?");

  const scopeType = String(row.scope_type ?? "").trim().toUpperCase();
  let scopeTarget = "-";
  if (scopeType === "DEPARTMENT") scopeTarget = String(row.scope_department_id ?? "?");
  else if (scopeType === "DEPARTMENT_GROUP") {
    scopeTarget = String(row.scope_department_group_id ?? "?");
  }

  const tasks = row.can_view_tasks ? "1" : "0";
  return `${targetType}|${targetId}|${scopeType}|${scopeTarget}|${tasks}`;
}

export function buildVisibilityAssignmentDuplicateMap(
  items: VisibilityAssignmentRecordLike[],
): Map<string, number> {
  const counts = new Map<string, number>();
  for (const row of items) {
    const key = visibilityAssignmentDedupeKey(row);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return counts;
}

export function isDuplicateVisibilityAssignment(
  row: VisibilityAssignmentRecordLike,
  duplicateCounts: ReadonlyMap<string, number>,
): boolean {
  return (duplicateCounts.get(visibilityAssignmentDedupeKey(row)) ?? 0) > 1;
}

export function summarizeVisibilityAssignments(
  items: VisibilityAssignmentRecordLike[],
): VisibilityAssignmentSummary {
  let activeCount = 0;
  let revokedCount = 0;
  let userCount = 0;
  let positionCount = 0;
  let departmentCount = 0;

  for (const row of items) {
    if (row.is_active) activeCount += 1;
    else revokedCount += 1;

    const targetType = String(row.target_type ?? "").trim().toUpperCase();
    if (targetType === "USER") userCount += 1;
    else if (targetType === "POSITION") positionCount += 1;
    else if (targetType === "DEPARTMENT") departmentCount += 1;
  }

  const duplicateCounts = buildVisibilityAssignmentDuplicateMap(items);
  let duplicateGroupCount = 0;
  for (const count of duplicateCounts.values()) {
    if (count > 1) duplicateGroupCount += 1;
  }

  return {
    activeCount,
    revokedCount,
    userCount,
    positionCount,
    departmentCount,
    duplicateGroupCount,
  };
}

export function sortVisibilityAssignmentsForDisplay<T extends VisibilityAssignmentRecordLike>(
  items: T[],
): T[] {
  return [...items].sort((a, b) => {
    const keyCmp = visibilityAssignmentDedupeKey(a).localeCompare(
      visibilityAssignmentDedupeKey(b),
      "ru",
    );
    if (keyCmp !== 0) return keyCmp;
    return Number(b.assignment_id ?? 0) - Number(a.assignment_id ?? 0);
  });
}

export type VisibilityTargetReferenceMaps = {
  usersById: ReadonlyMap<number, { fullName: string; login: string | null }>;
  departmentsById: ReadonlyMap<number, { name: string; groupName: string | null }>;
  positionsById: ReadonlyMap<number, { name: string }>;
};

export type VisibilityTargetDisplay = {
  primary: string;
  secondary: string | null;
  fallback: string;
  resolved: boolean;
};

export type PositionReferenceLike = {
  id?: number | null;
  position_id?: number | null;
  name?: string | null;
};

function positionIdOf(row: PositionReferenceLike): number {
  return Number(row.position_id ?? row.id ?? 0);
}

export function buildVisibilityTargetReferenceMaps(args: {
  adminUsers: AdminUser[];
  orgUnits: OrgUnitOption[];
  positions: PositionReferenceLike[];
}): VisibilityTargetReferenceMaps {
  const usersById = new Map<number, { fullName: string; login: string | null }>();
  for (const user of args.adminUsers) {
    const userId = Number(user.user_id ?? 0);
    if (!Number.isFinite(userId) || userId < 1) continue;
    const fullName = String(user.full_name ?? "").trim();
    const login = String(user.login ?? "").trim() || null;
    usersById.set(userId, {
      fullName: fullName || login || `User #${userId}`,
      login,
    });
  }

  const departmentsById = new Map<number, { name: string; groupName: string | null }>();
  for (const dept of args.orgUnits) {
    departmentsById.set(dept.unitId, {
      name: dept.name,
      groupName: dept.groupName ?? null,
    });
  }

  const positionsById = new Map<number, { name: string }>();
  for (const row of args.positions) {
    const positionId = positionIdOf(row);
    if (!Number.isFinite(positionId) || positionId < 1) continue;
    const name = String(row.name ?? "").trim();
    if (!name) continue;
    positionsById.set(positionId, { name });
  }

  return { usersById, departmentsById, positionsById };
}

export function resolveVisibilityTargetDisplay(
  row: VisibilityAssignmentRowLike,
  refs: VisibilityTargetReferenceMaps,
): VisibilityTargetDisplay {
  const targetType = String(row.target_type ?? "").trim().toUpperCase();

  if (targetType === "USER") {
    const userId = Number(row.target_user_id ?? 0);
    const fallback = `USER #${Number.isFinite(userId) && userId >= 1 ? userId : "?"}`;
    const user = Number.isFinite(userId) && userId >= 1 ? refs.usersById.get(userId) : undefined;
    if (!user) {
      return { primary: fallback, secondary: null, fallback, resolved: false };
    }
    return {
      primary: user.fullName,
      secondary: user.login ? `(${user.login})` : null,
      fallback,
      resolved: true,
    };
  }

  if (targetType === "DEPARTMENT") {
    const departmentId = Number(row.target_department_id ?? 0);
    const fallback = `DEPARTMENT #${Number.isFinite(departmentId) && departmentId >= 1 ? departmentId : "?"}`;
    const dept =
      Number.isFinite(departmentId) && departmentId >= 1
        ? refs.departmentsById.get(departmentId)
        : undefined;
    if (!dept) {
      return { primary: fallback, secondary: null, fallback, resolved: false };
    }
    return {
      primary: dept.name,
      secondary: dept.groupName,
      fallback,
      resolved: true,
    };
  }

  if (targetType === "POSITION") {
    const positionId = Number(row.target_position_id ?? 0);
    const fallback = `POSITION #${Number.isFinite(positionId) && positionId >= 1 ? positionId : "?"}`;
    const position =
      Number.isFinite(positionId) && positionId >= 1
        ? refs.positionsById.get(positionId)
        : undefined;
    if (!position) {
      return { primary: fallback, secondary: null, fallback, resolved: false };
    }
    return {
      primary: position.name,
      secondary: null,
      fallback,
      resolved: true,
    };
  }

  const fallback = targetType || "?";
  return { primary: fallback, secondary: null, fallback, resolved: false };
}
