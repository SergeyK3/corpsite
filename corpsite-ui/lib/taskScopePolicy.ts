import type { MeInfo } from "./types";

/** System administrator — task UI admin actions (delete, edit override). */
export function isTaskSystemAdmin(me: MeInfo | null | undefined): boolean {
  if (!me) return false;

  const roleId = Number(me.role_id ?? 0);
  const roleCode = String(me.role_code ?? "").trim().toUpperCase();
  const roleName = String(me.role_name ?? "").trim().toLowerCase();
  const roleNameRu = String(me.role_name_ru ?? "").trim().toLowerCase();

  if (roleId === 2) return true;
  if (me.is_system_admin === true) return true;
  if (roleCode === "ADMIN" || roleCode === "SYSTEM_ADMIN") return true;
  if (roleName.includes("system administrator")) return true;
  if (roleNameRu.includes("системный администратор")) return true;

  return false;
}

function matchesManagerRoleCode(roleCode: string): boolean {
  if (!roleCode) return false;
  if (roleCode.includes("DIRECTOR")) return true;
  if (roleCode.includes("DEPUTY")) return true;
  if (roleCode.endsWith("_HEAD")) return true;
  return false;
}

function matchesManagerRoleNameRu(roleNameRu: string): boolean {
  if (!roleNameRu) return false;
  if (roleNameRu.includes("руководител")) return true;
  if (roleNameRu.includes("директор")) return true;
  if (roleNameRu.includes("зам")) return true;
  return false;
}

/**
 * Whether the tasks page should show the «Все задачи» (team scope) tab.
 * Independent of edit policy — read-only team view is allowed for managers.
 */
export function canSeeTeamTasks(me: MeInfo | null | undefined): boolean {
  if (!me) return false;

  if (isTaskSystemAdmin(me)) return true;

  if (me.personnel_visibility?.can_view_tasks === true) return true;

  const roleCode = String(me.role_code ?? "").trim().toUpperCase();
  if (matchesManagerRoleCode(roleCode)) return true;

  const roleNameRu = String(me.role_name_ru ?? "").trim().toLowerCase();
  if (matchesManagerRoleNameRu(roleNameRu)) return true;

  return false;
}
