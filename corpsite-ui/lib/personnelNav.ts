// FILE: corpsite-ui/lib/personnelNav.ts
import type { MeInfo } from "./types";

function isSystemAdminRole(me: MeInfo | null | undefined): boolean {
  return Number(me?.role_id ?? 0) === 2;
}

/** Read-only «Персонал» — management-facing personnel browser (ADR-042 E1 + admin + HR). */
export function canSeePersonnelDirectoryNav(me: MeInfo | null | undefined): boolean {
  if (isSystemAdminRole(me)) return true;
  if (me?.is_privileged === true) return true;
  if (me?.has_personnel_admin === true) return true;
  return me?.show_org_sidebar === true || me?.has_personnel_visibility === true;
}

/** «Кадровые процессы» — HR operational contour (HR enrollment manager or sysadmin). */
export function canSeeHrProcessesNav(me: MeInfo | null | undefined): boolean {
  if (isSystemAdminRole(me)) return true;
  if (me?.is_privileged === true) return true;
  return me?.has_personnel_admin === true;
}

export function isPersonnelDirectoryRoute(pathname: string): boolean {
  return (
    pathname === "/directory/staff" ||
    pathname.startsWith("/directory/staff/") ||
    pathname === "/directory/employees" ||
    pathname.startsWith("/directory/employees/")
  );
}

export function isHrProcessesRoute(pathname: string): boolean {
  return pathname === "/directory/personnel" || pathname.startsWith("/directory/personnel/");
}

export const PERSONNEL_DIRECTORY_NAV_HREF = "/directory/staff";
export const HR_PROCESSES_NAV_HREF = "/directory/personnel/journal";

/** Legacy /directory/personnel bookmark — HR journal vs management staff vs tasks fallback. */
export function resolvePersonnelRootRedirect(me: MeInfo | null | undefined): string {
  if (canSeeHrProcessesNav(me)) return HR_PROCESSES_NAV_HREF;
  if (canSeePersonnelDirectoryNav(me)) return PERSONNEL_DIRECTORY_NAV_HREF;
  return "/tasks";
}
