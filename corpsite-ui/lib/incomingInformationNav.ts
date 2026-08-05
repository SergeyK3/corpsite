import type { MeInfo } from "./types";

export const INCOMING_INFORMATION_NAV_HREF = "/directory/incoming-information";

export type IncomingInformationNavItem = {
  href: string;
  title: string;
  matchPrefixes: string[];
};

export const INCOMING_INFORMATION_NAV_ITEM: IncomingInformationNavItem = {
  href: INCOMING_INFORMATION_NAV_HREF,
  title: "Входящая информация",
  matchPrefixes: [INCOMING_INFORMATION_NAV_HREF],
};

export function isIncomingInformationRoute(pathname: string): boolean {
  return (
    pathname === INCOMING_INFORMATION_NAV_HREF ||
    pathname.startsWith(`${INCOMING_INFORMATION_NAV_HREF}/`)
  );
}

/** Canonical frontend gate: do not infer access from role, admin, privilege or org scope. */
export function canSeeIncomingInformationNav(me: MeInfo | null | undefined): boolean {
  return me?.has_incoming_information_read === true;
}

export function canAccessIncomingInformationRoute(me: MeInfo | null | undefined): boolean {
  return canSeeIncomingInformationNav(me);
}
