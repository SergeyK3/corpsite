import type { MeInfo, TaskScope } from "./types";

/** System administrator — task UI admin actions (delete, edit override). */
export function isTaskSystemAdmin(me: MeInfo | null | undefined): boolean {
  return Number(me?.role_id ?? 0) === 2;
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
