// FILE: corpsite-ui/lib/personnelNav.test.ts
import { describe, expect, it } from "vitest";

import type { MeInfo } from "./types";
import { canSeeSysadminCabinetNav } from "./adminNav";
import {
  buildDirectorySidebarNavItems,
  buildPersonnelSidebarNavItems,
  buildVisibilityDirectoryNavItems,
  canSeeHrProcessesNav,
  canSeePersonnelDirectoryNav,
  HR_PROCESSES_NAV_HREF,
  HR_PROCESSES_NAV_ITEM,
  isDirectorySidebarNavItemActive,
  isHrProcessesRoute,
  isPersonnelDirectoryRoute,
  isPersonnelDirectoryNavItem,
  PERSONNEL_DIRECTORY_NAV_HREF,
  PERSONNEL_DIRECTORY_NAV_ITEM,
  resolveDirectoryOrgTreeBasePath,
  resolvePersonnelRootRedirect,
} from "./personnelNav";

describe("personnelNav", () => {
  const systemAdmin: MeInfo = { user_id: 1, role_id: 2 };
  const privileged: MeInfo = { user_id: 2, role_id: 3, is_privileged: true };
  const hrManager: MeInfo = { user_id: 4, role_id: 3, has_personnel_admin: true };
  const headWithVisibility: MeInfo = {
    user_id: 5,
    role_id: 3,
    has_personnel_visibility: true,
    show_org_sidebar: true,
  };
  const directorLike: MeInfo = {
    user_id: 6,
    role_id: 3,
    has_personnel_visibility: true,
    show_org_sidebar: true,
    personnel_visibility: { organization_wide: true },
  };
  const regular: MeInfo = { user_id: 7, role_id: 3 };

  it("canSeePersonnelDirectoryNav for managers and admins", () => {
    expect(canSeePersonnelDirectoryNav(systemAdmin)).toBe(true);
    expect(canSeePersonnelDirectoryNav(headWithVisibility)).toBe(true);
    expect(canSeePersonnelDirectoryNav(directorLike)).toBe(true);
    expect(canSeePersonnelDirectoryNav(hrManager)).toBe(true);
    expect(canSeePersonnelDirectoryNav(regular)).toBe(false);
  });

  it("canSeeHrProcessesNav for HR and sysadmin only", () => {
    expect(canSeeHrProcessesNav(systemAdmin)).toBe(true);
    expect(canSeeHrProcessesNav(privileged)).toBe(true);
    expect(canSeeHrProcessesNav(hrManager)).toBe(true);
    expect(canSeeHrProcessesNav(headWithVisibility)).toBe(false);
    expect(canSeeHrProcessesNav(directorLike)).toBe(false);
    expect(canSeeHrProcessesNav(regular)).toBe(false);
  });

  it("route helpers distinguish staff vs HR processes", () => {
    expect(isPersonnelDirectoryRoute("/directory/staff")).toBe(true);
    expect(isPersonnelDirectoryRoute("/directory/staff/42")).toBe(true);
    expect(isHrProcessesRoute("/directory/personnel/journal")).toBe(true);
    expect(isHrProcessesRoute("/directory/personnel/import")).toBe(true);
    expect(isHrProcessesRoute("/directory/personnel/applicants")).toBe(true);
    expect(isPersonnelDirectoryRoute("/directory/personnel/journal")).toBe(false);
    expect(isHrProcessesRoute("/directory/staff")).toBe(false);
  });

  it("resolvePersonnelRootRedirect sends HR to journal and managers to staff", () => {
    expect(resolvePersonnelRootRedirect(systemAdmin)).toBe("/directory/personnel/journal");
    expect(resolvePersonnelRootRedirect(privileged)).toBe("/directory/personnel/journal");
    expect(resolvePersonnelRootRedirect(hrManager)).toBe("/directory/personnel/journal");
    expect(resolvePersonnelRootRedirect(headWithVisibility)).toBe("/directory/staff");
    expect(resolvePersonnelRootRedirect(directorLike)).toBe("/directory/staff");
    expect(resolvePersonnelRootRedirect(regular)).toBe("/tasks");
  });

  it("resolvePersonnelRootRedirect prefers HR journal when user has both HR and visibility", () => {
    const hrWithVisibility: MeInfo = {
      user_id: 8,
      role_id: 3,
      has_personnel_admin: true,
      has_personnel_visibility: true,
      show_org_sidebar: true,
    };
    expect(resolvePersonnelRootRedirect(hrWithVisibility)).toBe("/directory/personnel/journal");
  });

  describe("ADR-045 sidebar nav contract", () => {
    function findNav(title: string, items: { title: string; href: string }[]) {
      return items.find((item) => item.title === title);
    }

    it("System Administrator sees Персонал → staff and Кадровые процессы → journal", () => {
      const items = buildPersonnelSidebarNavItems(systemAdmin);
      expect(findNav("Персонал", items)?.href).toBe("/directory/staff");
      expect(findNav("Кадровые процессы", items)?.href).toBe("/directory/personnel/journal");
      expect(items.filter((item) => item.title === "Персонал")).toHaveLength(1);
      expect(items.some((item) => item.title === "Персонал" && item.href.startsWith("/directory/personnel"))).toBe(
        false,
      );
    });

    it("privileged System Administrator gets the same personnel split items", () => {
      const items = buildPersonnelSidebarNavItems(privileged);
      expect(findNav("Персонал", items)?.href).toBe(PERSONNEL_DIRECTORY_NAV_HREF);
      expect(findNav("Кадровые процессы", items)?.href).toBe(HR_PROCESSES_NAV_HREF);
    });

    it("HR sees both personnel items but not System Administrator cabinet", () => {
      const items = buildPersonnelSidebarNavItems(hrManager);
      expect(findNav("Персонал", items)?.href).toBe("/directory/staff");
      expect(findNav("Кадровые процессы", items)?.href).toBe("/directory/personnel/journal");
      expect(canSeeSysadminCabinetNav(hrManager)).toBe(false);
    });

    it("visibility user sees only read-only Персонал in directory nav", () => {
      const items = buildVisibilityDirectoryNavItems(headWithVisibility);
      expect(findNav("Персонал", items)?.href).toBe("/directory/staff");
      expect(findNav("Кадровые процессы", items)).toBeUndefined();
      expect(findNav("Контакты", items)?.href).toBe("/directory/contacts");
      expect(canSeeSysadminCabinetNav(headWithVisibility)).toBe(false);
    });

    it("HR head visibility shell matches sysadmin personnel split without directory extras", () => {
      const items = buildVisibilityDirectoryNavItems(hrManager);
      expect(items.map((item) => item.title)).toEqual(["Персонал", "Кадровые процессы"]);
    });

    it("Operational Orders is a sibling node, not nested under HR personnel items", () => {
      const personnelOnly = buildPersonnelSidebarNavItems(hrManager);
      expect(personnelOnly.map((item) => item.title)).toEqual(["Персонал", "Кадровые процессы"]);
      expect(personnelOnly.some((item) => item.title === "Производственные приказы")).toBe(false);

      const withOo = buildDirectorySidebarNavItems({
        ...hrManager,
        has_operational_orders_read: true,
      });
      expect(withOo.map((item) => item.title)).toEqual([
        "Персонал",
        "Кадровые процессы",
        "Производственные приказы",
      ]);
      expect(withOo[2]?.iconId).toBeUndefined();
    });

    it("visibility user with OO read sees OO after personnel and before contacts", () => {
      const items = buildVisibilityDirectoryNavItems({
        ...headWithVisibility,
        has_operational_orders_read: true,
      });
      expect(items.map((item) => item.title)).toEqual([
        "Персонал",
        "Производственные приказы",
        "Контакты",
        "Должности",
      ]);
    });

    it("nav item constants are not cross-wired", () => {
      expect(PERSONNEL_DIRECTORY_NAV_ITEM.title).toBe("Персонал");
      expect(PERSONNEL_DIRECTORY_NAV_ITEM.href).toBe("/directory/staff");
      expect(HR_PROCESSES_NAV_ITEM.title).toBe("Кадровые процессы");
      expect(HR_PROCESSES_NAV_ITEM.href).toBe("/directory/personnel/journal");
      expect(isPersonnelDirectoryNavItem(PERSONNEL_DIRECTORY_NAV_ITEM)).toBe(true);
      expect(isPersonnelDirectoryNavItem(HR_PROCESSES_NAV_ITEM)).toBe(false);
    });

    it("org tree base path keeps legacy /directory/employees on staff", () => {
      expect(resolveDirectoryOrgTreeBasePath("/directory/employees")).toBe("/directory/staff");
      expect(resolveDirectoryOrgTreeBasePath("/directory/staff")).toBe("/directory/staff");
      expect(resolveDirectoryOrgTreeBasePath("/directory/personnel/journal")).toBe("/directory/personnel");
      expect(resolveDirectoryOrgTreeBasePath("/directory/personnel/applicants")).toBe(
        "/directory/personnel/applicants",
      );
    });

    it("active state highlights HR processes on applicants route", () => {
      expect(
        isDirectorySidebarNavItemActive("/directory/personnel/applicants", HR_PROCESSES_NAV_ITEM),
      ).toBe(true);
    });

    it("active state does not cross-highlight staff vs HR routes", () => {
      expect(isDirectorySidebarNavItemActive("/directory/staff", PERSONNEL_DIRECTORY_NAV_ITEM)).toBe(true);
      expect(isDirectorySidebarNavItemActive("/directory/staff", HR_PROCESSES_NAV_ITEM)).toBe(false);
      expect(isDirectorySidebarNavItemActive("/directory/personnel/journal", HR_PROCESSES_NAV_ITEM)).toBe(true);
      expect(isDirectorySidebarNavItemActive("/directory/personnel/journal", PERSONNEL_DIRECTORY_NAV_ITEM)).toBe(
        false,
      );
    });
  });
});
