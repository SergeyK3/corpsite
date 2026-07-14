// FILE: corpsite-ui/lib/visibilityNav.ts
import type { MeInfo } from "./types";

import { canSeeAdminShell } from "./adminNav";
import { isPositionCabinetRoute } from "./positionCabinetNav";
import {
  canSeeHrProcessesNav,
  canSeePersonnelDirectoryNav,
  isHrProcessesRoute,
  isPersonnelDirectoryRoute,
  PERSONNEL_DIRECTORY_NAV_ITEM,
} from "./personnelNav";
import { canSeeOperationalOrdersNav, isOperationalOrdersRoute } from "./operationalOrdersNav";

/** ADR-042 E1 assignment / org-sidebar flag (excludes HR-only operational contour). */
export function hasE1PersonnelVisibility(me: MeInfo | null | undefined): boolean {
  return me?.show_org_sidebar === true || me?.has_personnel_visibility === true;
}

/** ADR-042 E1 — org sidebar / personnel directory (not full admin shell). */
export function hasPersonnelVisibility(me: MeInfo | null | undefined): boolean {
  if (canSeeAdminShell(me)) return true;
  if (canSeeHrProcessesNav(me)) return true;
  return hasE1PersonnelVisibility(me);
}

export function canViewPersonnelTasksReadOnly(me: MeInfo | null | undefined): boolean {
  if (canSeeAdminShell(me)) return true;
  return me?.personnel_visibility?.can_view_tasks === true;
}

export function canAccessDirectoryRoute(pathname: string, me: MeInfo | null | undefined): boolean {
  if (canSeeAdminShell(me)) return true;

  if (isHrProcessesRoute(pathname)) return canSeeHrProcessesNav(me);
  if (isPersonnelDirectoryRoute(pathname)) return canSeePersonnelDirectoryNav(me);
  if (isOperationalOrdersRoute(pathname)) return canSeeOperationalOrdersNav(me);

  if (isPositionCabinetRoute(pathname)) {
    if (pathname.startsWith("/tasks") && hasPersonnelVisibility(me) && !canViewPersonnelTasksReadOnly(me)) {
      return false;
    }
    return true;
  }

  if (!hasPersonnelVisibility(me)) return false;

  if (pathname.startsWith("/directory")) return true;
  if (pathname.startsWith("/tasks") && canViewPersonnelTasksReadOnly(me)) return true;
  if (pathname === "/profile" || pathname.startsWith("/profile/")) return true;
  return false;
}

export function shouldShowOrgUnitsPanel(
  pathname: string,
  me: MeInfo | null | undefined,
): boolean {
  if (!hasPersonnelVisibility(me)) return false;

  if (pathname.startsWith("/directory/department-groups")) return false;
  if (pathname.startsWith("/directory/org-units")) return false;
  if (pathname.startsWith("/admin/system/org-units")) return false;

  if (canSeeAdminShell(me)) {
    return (
      pathname.startsWith("/tasks") ||
      pathname.startsWith("/dashboards") ||
      pathname.startsWith("/education") ||
      pathname.startsWith("/admin/regular-tasks") ||
      pathname.startsWith("/regular-tasks") ||
      pathname.startsWith("/directory")
    );
  }

  return (
    pathname.startsWith("/tasks") ||
    pathname.startsWith("/dashboards") ||
    pathname.startsWith("/education") ||
    pathname.startsWith("/directory")
  );
}

export type VisibilityNavItem = {
  href: string;
  title: string;
  matchPrefixes: string[];
};

export const VISIBILITY_DIRECTORY_NAV: VisibilityNavItem[] = [
  PERSONNEL_DIRECTORY_NAV_ITEM,
  {
    href: "/directory/contacts",
    title: "Контакты",
    matchPrefixes: ["/directory/contacts"],
  },
  {
    href: "/directory/positions",
    title: "Должности",
    matchPrefixes: ["/directory/positions"],
  },
];