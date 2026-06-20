// FILE: corpsite-ui/lib/adminNav.ts
import type { MeInfo } from "./types";

/** Task/directory admin shell — unchanged: system admin role only. */
export function isSystemAdminRole(me: MeInfo | null | undefined): boolean {
  return Number(me?.role_id ?? 0) === 2;
}

/**
 * Backend-aligned privileged operator (role_id=2 OR env allowlist on server).
 * Does NOT include SYSADMIN_CABINET grant until C2.
 */
export function isPrivilegedOperator(me: MeInfo | null | undefined): boolean {
  if (isSystemAdminRole(me)) return true;
  return me?.is_privileged === true;
}

/** Full admin sidebar (directory, sync, regular-tasks) — role_id=2 only. */
export function canSeeAdminShell(me: MeInfo | null | undefined): boolean {
  return isSystemAdminRole(me);
}

/** Sysadmin cabinet nav — aligned with backend require_sysadmin_api legacy path. */
export function canSeeSysadminCabinetNav(me: MeInfo | null | undefined): boolean {
  return isPrivilegedOperator(me);
}

export function isForbiddenAdminRoute(
  pathname: string,
  me: MeInfo | null | undefined,
): boolean {
  if (pathname.startsWith("/admin/system")) {
    return !canSeeSysadminCabinetNav(me);
  }
  if (
    pathname.startsWith("/directory") ||
    pathname.startsWith("/regular-tasks") ||
    pathname.startsWith("/admin")
  ) {
    return !canSeeAdminShell(me);
  }
  return false;
}
