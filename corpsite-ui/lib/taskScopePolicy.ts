import type { MeInfo, TaskScope } from "./types";

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

/**
 * Whether the tasks page should show the «Все задачи» (team scope) tab.
 * Source of truth: GET /auth/me → can_view_all_tasks (mirrors backend can_view_team_tasks).
 */
export function canSeeTeamTasks(me: MeInfo | null | undefined): boolean {
  return me?.can_view_all_tasks === true;
}

/** Default tasks list scope after /auth/me — «Мои задачи» unless backend grants all-tasks. */
export function defaultTaskScope(me: MeInfo | null | undefined): TaskScope {
  return canSeeTeamTasks(me) ? "team" : "mine";
}
