import type { MeInfo } from "./types";

/**
 * Mirrors backend DELETE /directory/employees/{id} guard (is_system_admin only).
 * Prefer explicit /auth/me flag; fall back to canonical is_system_admin.
 */
export function canHardDeleteEmployee(me: MeInfo | null | undefined): boolean {
  if (me?.can_hard_delete_employee === true) return true;
  return me?.is_system_admin === true;
}
