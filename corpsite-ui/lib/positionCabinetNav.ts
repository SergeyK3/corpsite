// FILE: corpsite-ui/lib/positionCabinetNav.ts

import { isHrProcessesRoute } from "./personnelNav";

/** Position Cabinet section identifiers (UI shell only — no backend binding yet). */
export type PositionCabinetSection = "tasks" | "dashboards" | "education";

export type PositionCabinetNavItem = {
  id: PositionCabinetSection;
  href: string;
  /** Visible tab caption (also exposed as `title` for nav consistency). */
  label: string;
  title: string;
  /**
   * Architectural ownership (ARCH-001 / Position Cabinet):
   * - dashboards: bound to Position Cabinet; survives occupant change.
   * - education: bound to Employee; follows current cabinet occupant.
   * - tasks: existing subsystem (unchanged in this phase).
   */
  ownership: "position_cabinet" | "employee" | "existing";
};

/** Single source of truth for Position Cabinet section tab captions. */
export const POSITION_CABINET_TAB_LABELS: Record<PositionCabinetSection, string> = {
  tasks: "Мои задачи",
  dashboards: "Дашборды",
  education: "Образование",
};

export function getPositionCabinetTabLabel(section: PositionCabinetSection): string {
  return POSITION_CABINET_TAB_LABELS[section];
}

function buildNavItem(
  id: PositionCabinetSection,
  href: string,
  ownership: PositionCabinetNavItem["ownership"],
): PositionCabinetNavItem {
  const label = getPositionCabinetTabLabel(id);
  return { id, href, label, title: label, ownership };
}

export const POSITION_CABINET_NAV_ITEMS: PositionCabinetNavItem[] = [
  buildNavItem("tasks", "/tasks", "existing"),
  buildNavItem("dashboards", "/dashboards", "position_cabinet"),
  buildNavItem("education", "/education", "employee"),
];

const SECTION_BY_PATH: Array<{ prefix: string; section: PositionCabinetSection }> = [
  { prefix: "/tasks", section: "tasks" },
  { prefix: "/dashboards", section: "dashboards" },
  { prefix: "/education", section: "education" },
];

export function isPositionCabinetRoute(pathname: string): boolean {
  return SECTION_BY_PATH.some(
    ({ prefix }) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export function resolvePositionCabinetSection(pathname: string): PositionCabinetSection | null {
  const match = SECTION_BY_PATH.find(
    ({ prefix }) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  return match?.section ?? null;
}

export type ShouldShowPositionCabinetNavOptions = {
  showPersonnelVisibility: boolean;
};

/** Whether AppShell should render Position Cabinet top nav (tabs + library links). */
export function shouldShowPositionCabinetNav(
  pathname: string,
  options: ShouldShowPositionCabinetNavOptions,
): boolean {
  if (isPositionCabinetRoute(pathname)) return true;
  if (options.showPersonnelVisibility && isHrProcessesRoute(pathname)) return true;
  return false;
}
