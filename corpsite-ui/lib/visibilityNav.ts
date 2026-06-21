// FILE: corpsite-ui/lib/visibilityNav.ts
import type { MeInfo } from "./types";

import { canSeeAdminShell } from "./adminNav";

/** ADR-042 E1 — org sidebar / personnel directory (not full admin shell). */
export function hasPersonnelVisibility(me: MeInfo | null | undefined): boolean {
  if (canSeeAdminShell(me)) return true;
  return me?.show_org_sidebar === true || me?.has_personnel_visibility === true;
}

export function canViewPersonnelTasksReadOnly(me: MeInfo | null | undefined): boolean {
  if (canSeeAdminShell(me)) return true;
  return me?.personnel_visibility?.can_view_tasks === true;
}

export function canAccessDirectoryRoute(pathname: string, me: MeInfo | null | undefined): boolean {
  if (canSeeAdminShell(me)) return true;
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

  if (canSeeAdminShell(me)) {
    return (
      pathname.startsWith("/tasks") ||
      pathname.startsWith("/admin/regular-tasks") ||
      pathname.startsWith("/regular-tasks") ||
      pathname.startsWith("/directory")
    );
  }

  return pathname.startsWith("/tasks") || pathname.startsWith("/directory");
}

export const VISIBILITY_DIRECTORY_NAV = [
  {
    href: "/directory/personnel",
    title: "Персонал",
    matchPrefixes: ["/directory/personnel", "/directory/employees"],
  },
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
] as const;
