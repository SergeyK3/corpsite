// FILE: corpsite-ui/lib/personnelNav.ts
import type { MeInfo } from "./types";
import { canSeeOperationalOrdersNav, OPERATIONAL_ORDERS_NAV_ITEM } from "./operationalOrdersNav";

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
  return (
    pathname === "/directory/personnel" ||
    pathname.startsWith("/directory/personnel/") ||
    pathname === "/directory/personnel-applications" ||
    pathname.startsWith("/directory/personnel-applications/")
  );
}

export const PERSONNEL_DIRECTORY_NAV_HREF = "/directory/staff";
export const HR_PROCESSES_NAV_HREF = "/directory/personnel/journal";

export type PersonnelNavItem = {
  href: string;
  title: string;
  matchPrefixes: string[];
  iconId?: "operational-orders";
};

/** Read-only «Персонал» sidebar item (ADR-045). */
export const PERSONNEL_DIRECTORY_NAV_ITEM: PersonnelNavItem = {
  href: PERSONNEL_DIRECTORY_NAV_HREF,
  title: "Персонал",
  matchPrefixes: ["/directory/staff", "/directory/employees"],
};

/** HR operational contour sidebar item (ADR-045). */
export const HR_PROCESSES_NAV_ITEM: PersonnelNavItem = {
  href: HR_PROCESSES_NAV_HREF,
  title: "Кадровые процессы",
  matchPrefixes: ["/directory/personnel", "/directory/personnel-applications"],
};

export function isPersonnelDirectoryNavItem(item: Pick<PersonnelNavItem, "href" | "title">): boolean {
  return item.href === PERSONNEL_DIRECTORY_NAV_HREF || item.title === PERSONNEL_DIRECTORY_NAV_ITEM.title;
}

export function isHrProcessesNavItem(item: Pick<PersonnelNavItem, "href" | "title">): boolean {
  return (
    item.title === HR_PROCESSES_NAV_ITEM.title ||
    item.href === HR_PROCESSES_NAV_HREF ||
    (item.href.startsWith("/directory/personnel") && item.title !== PERSONNEL_DIRECTORY_NAV_ITEM.title)
  );
}

/** Personnel + HR items only — Operational Orders is a separate document domain (OO-UI-001B). */
export function buildPersonnelSidebarNavItems(me: MeInfo | null | undefined): PersonnelNavItem[] {
  const items: PersonnelNavItem[] = [];
  if (canSeePersonnelDirectoryNav(me)) items.push(PERSONNEL_DIRECTORY_NAV_ITEM);
  if (canSeeHrProcessesNav(me)) items.push(HR_PROCESSES_NAV_ITEM);
  return items;
}

export function isOperationalOrdersNavItem(item: Pick<PersonnelNavItem, "href">): boolean {
  return item.href === OPERATIONAL_ORDERS_NAV_ITEM.href;
}

/**
 * Directory sidebar: Персонал → Кадровые процессы → Производственные приказы → Контакты → Должности.
 * Operational Orders is a sibling top-level node, not nested under HR.
 */
export function buildDirectorySidebarNavItems(
  me: MeInfo | null | undefined,
  opts?: { includeTasksReadOnly?: boolean; includeVisibilityExtras?: boolean },
): VisibilityDirectoryNavItem[] {
  const items: VisibilityDirectoryNavItem[] = [];
  if (opts?.includeTasksReadOnly) {
    items.push({
      href: "/tasks",
      title: "Задачи (просмотр)",
      matchPrefixes: ["/tasks"],
    });
  }
  items.push(...buildPersonnelSidebarNavItems(me));
  if (canSeeOperationalOrdersNav(me)) {
    items.push(OPERATIONAL_ORDERS_NAV_ITEM);
  }
  if (opts?.includeVisibilityExtras !== false) {
    if (me?.show_org_sidebar === true || me?.has_personnel_visibility === true) {
      items.push(...VISIBILITY_DIRECTORY_EXTRAS);
    }
  }
  return items;
}

export type VisibilityDirectoryNavItem = PersonnelNavItem;

const VISIBILITY_DIRECTORY_EXTRAS: VisibilityDirectoryNavItem[] = [
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

export function buildVisibilityDirectoryNavItems(
  me: MeInfo | null | undefined,
  opts?: { includeTasksReadOnly?: boolean },
): VisibilityDirectoryNavItem[] {
  return buildDirectorySidebarNavItems(me, {
    includeTasksReadOnly: opts?.includeTasksReadOnly,
    includeVisibilityExtras: true,
  });
}

export function shouldShowPrimaryAdminNavItem(
  item: Pick<PersonnelNavItem, "href" | "title">,
  me: MeInfo | null | undefined,
  opts: { isAdmin: boolean; showSysadminNav: boolean; showPersonnelLifecycleNav: boolean; showPersonnelIdentityOperationsNav: boolean },
): boolean {
  if (item.href === "/admin/system/personnel-lifecycle") return opts.showPersonnelLifecycleNav;
  if (item.href === "/admin/system/personnel-identity/operations") {
    return opts.showPersonnelIdentityOperationsNav;
  }
  if (item.href === "/admin/system/org-units") return opts.showSysadminNav;
  if (item.href === "/admin/system") return opts.showSysadminNav;
  if (isPersonnelDirectoryNavItem(item)) return canSeePersonnelDirectoryNav(me);
  if (isHrProcessesNavItem(item)) return canSeeHrProcessesNav(me);
  if (isOperationalOrdersNavItem(item)) return canSeeOperationalOrdersNav(me);
  return opts.isAdmin;
}

export function isDirectorySidebarNavItemActive(pathname: string, item: PersonnelNavItem): boolean {
  const prefixes = item.matchPrefixes?.length ? item.matchPrefixes : [item.href];
  return prefixes.some((prefix) => {
    if (pathname === prefix) return true;
    if (!pathname.startsWith(`${prefix}/`)) return false;
    if (prefix === "/directory/personnel" && pathname.startsWith("/directory/staff")) {
      return false;
    }
    if (prefix === "/directory/staff" && pathname.startsWith("/directory/personnel")) {
      return false;
    }
    return true;
  });
}

export function resolveDirectoryOrgTreeBasePath(pathname: string): string {
  if (pathname.startsWith("/tasks")) return "/tasks";
  if (pathname.startsWith("/dashboards")) return "/dashboards";
  if (pathname.startsWith("/education")) return "/education";
  if (pathname.startsWith("/admin/regular-tasks/catch-up")) return "/admin/regular-tasks/catch-up";
  if (pathname.startsWith("/admin/regular-tasks")) return "/admin/regular-tasks";
  if (pathname.startsWith("/admin/system/org-units")) return "/admin/system/org-units";
  if (pathname.startsWith("/regular-tasks")) return "/regular-tasks";
  if (pathname.startsWith("/directory/staff")) return "/directory/staff";
  if (pathname.startsWith("/directory/roles")) return "/directory/roles";
  if (pathname.startsWith("/directory/positions")) return "/directory/positions";
  if (pathname.startsWith("/directory/contacts")) return "/directory/contacts";
  if (pathname.startsWith("/directory/personnel-applications")) return "/directory/personnel-applications";
  if (pathname.startsWith("/directory/personnel/applicants")) return "/directory/personnel/applicants";
  if (pathname.startsWith("/directory/personnel")) return "/directory/personnel";
  if (pathname.startsWith("/directory/operational-orders")) return "/directory/operational-orders";
  if (pathname.startsWith("/directory/working-contacts")) return "/directory/working-contacts";
  if (pathname.startsWith("/directory/org-units")) return "/directory/org-units";
  if (pathname.startsWith("/directory/org-unit-types")) return "/directory/org-units";
  if (pathname.startsWith("/directory/org")) return "/directory/org";
  if (pathname.startsWith("/directory/employees")) return "/directory/staff";
  return pathname;
}

/** Legacy /directory/personnel bookmark — HR journal vs management staff vs tasks fallback. */
export function resolvePersonnelRootRedirect(me: MeInfo | null | undefined): string {
  if (canSeeHrProcessesNav(me)) return HR_PROCESSES_NAV_HREF;
  if (canSeePersonnelDirectoryNav(me)) return PERSONNEL_DIRECTORY_NAV_HREF;
  return "/tasks";
}
