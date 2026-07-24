import type { MeInfo } from "@/lib/types";

import { canSeeOperationalOrdersNav as canSeeOoNav } from "@/app/directory/operational-orders/_lib/permissions";

export const OPERATIONAL_ORDERS_NAV_HREF = "/directory/operational-orders";

export type OperationalOrdersNavItem = {
  href: string;
  title: string;
  matchPrefixes: string[];
  /** Sidebar icon id — rendered by AppShell. */
  iconId?: "operational-orders";
};

export const OPERATIONAL_ORDERS_NAV_ITEM: OperationalOrdersNavItem = {
  href: OPERATIONAL_ORDERS_NAV_HREF,
  title: "Производственные приказы",
  matchPrefixes: ["/directory/operational-orders"],
};

export function isOperationalOrdersRoute(pathname: string): boolean {
  return pathname === OPERATIONAL_ORDERS_NAV_HREF || pathname.startsWith(`${OPERATIONAL_ORDERS_NAV_HREF}/`);
}

export function canSeeOperationalOrdersNav(me: MeInfo | null | undefined): boolean {
  return canSeeOoNav(me);
}

export function canAccessOperationalOrdersRoute(me: MeInfo | null | undefined): boolean {
  if (me?.is_privileged) return true;
  return canSeeOperationalOrdersNav(me);
}
