import { describe, expect, it } from "vitest";

import {
  buildOperationalOrdersAccessDiagnostics,
  explainOperationalOrdersSectionAccessDenied,
  formatAccessDiagnosticsForDeveloper,
  OO_SECTION_READ_PERMISSION,
} from "./accessDiagnostics";

describe("operational orders access diagnostics", () => {
  it("explains missing OO read for HR head without projection", () => {
    const explained = explainOperationalOrdersSectionAccessDenied({
      has_personnel_admin: true,
      has_operational_orders_read: false,
    });

    expect(explained.title).toContain("Производственные приказы");
    expect(explained.message).toContain("OPERATIONAL_ORDERS_INTAKE_READ");
    expect(explained.diagnostics.hasPersonnelAdmin).toBe(true);
    expect(explained.diagnostics.missingRecommendedPermissions).toEqual([OO_SECTION_READ_PERMISSION]);
  });

  it("formats developer diagnostics with projection flags", () => {
    const lines = formatAccessDiagnosticsForDeveloper(
      buildOperationalOrdersAccessDiagnostics({
        has_operational_orders_read: false,
        operational_orders_permissions: { intake_read: false, promote: true },
      }),
    );

    expect(lines.some((l) => l.includes("has_operational_orders_read: false"))).toBe(true);
    expect(lines.some((l) => l.includes("promote: true"))).toBe(true);
    expect(lines.some((l) => l.includes(OO_SECTION_READ_PERMISSION))).toBe(true);
  });
});
