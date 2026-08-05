import { describe, expect, it } from "vitest";

import {
  canAccessIncomingInformationRoute,
  canSeeIncomingInformationNav,
  INCOMING_INFORMATION_NAV_HREF,
  INCOMING_INFORMATION_NAV_ITEM,
  isIncomingInformationRoute,
} from "./incomingInformationNav";

describe("incomingInformationNav", () => {
  it("uses only the canonical aggregate projection", () => {
    expect(canSeeIncomingInformationNav({ has_incoming_information_read: true })).toBe(true);
    expect(canAccessIncomingInformationRoute({ has_incoming_information_read: true })).toBe(true);
    expect(canSeeIncomingInformationNav({ role_id: 2, is_system_admin: true })).toBe(false);
    expect(canSeeIncomingInformationNav({ is_privileged: true })).toBe(false);
    expect(canSeeIncomingInformationNav({ has_personnel_visibility: true })).toBe(false);
    expect(canSeeIncomingInformationNav(null)).toBe(false);
  });

  it("defines list and detail routes under one nav item", () => {
    expect(INCOMING_INFORMATION_NAV_ITEM).toEqual({
      href: INCOMING_INFORMATION_NAV_HREF,
      title: "Входящая информация",
      matchPrefixes: [INCOMING_INFORMATION_NAV_HREF],
    });
    expect(isIncomingInformationRoute(INCOMING_INFORMATION_NAV_HREF)).toBe(true);
    expect(isIncomingInformationRoute(`${INCOMING_INFORMATION_NAV_HREF}/documents/42`)).toBe(true);
    expect(isIncomingInformationRoute("/directory/operational-orders")).toBe(false);
  });
});
