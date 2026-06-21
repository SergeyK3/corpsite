// FILE: corpsite-ui/lib/adminNav.ts
import type { MeInfo } from "./types";
import { hasPersonnelVisibility } from "./visibilityNav";

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

/** ADR-043 C4.2 — personnel lifecycle section (ADMIN or HR_ENROLLMENT_MANAGER). */
export function canSeePersonnelLifecycleNav(me: MeInfo | null | undefined): boolean {
  if (canSeeSysadminCabinetNav(me)) return true;
  return me?.has_personnel_admin === true;
}

export function isPersonnelLifecycleRoute(pathname: string): boolean {
  return pathname === "/admin/system/personnel-lifecycle" || pathname.startsWith("/admin/system/personnel-lifecycle/");
}

/** ADR-044 R2.5g — personnel identity operations UI (personnel admin baseline). */
export function isPersonnelIdentityOperationsRoute(pathname: string): boolean {
  return (
    pathname === "/admin/system/personnel-identity/operations" ||
    pathname.startsWith("/admin/system/personnel-identity/")
  );
}

export function canSeePersonnelIdentityOperationsNav(me: MeInfo | null | undefined): boolean {
  return canSeePersonnelLifecycleNav(me);
}

export function isForbiddenAdminRoute(
  pathname: string,
  me: MeInfo | null | undefined,
): boolean {
  if (isPersonnelLifecycleRoute(pathname)) {
    return !canSeePersonnelLifecycleNav(me);
  }
  if (isPersonnelIdentityOperationsRoute(pathname)) {
    return !canSeePersonnelIdentityOperationsNav(me);
  }
  if (pathname.startsWith("/admin/system")) {
    return !canSeeSysadminCabinetNav(me);
  }
  if (
    pathname.startsWith("/directory") ||
    pathname.startsWith("/regular-tasks") ||
    pathname.startsWith("/admin")
  ) {
    if (pathname.startsWith("/directory") && hasPersonnelVisibility(me)) {
      return false;
    }
    return !canSeeAdminShell(me);
  }
  return false;
}
