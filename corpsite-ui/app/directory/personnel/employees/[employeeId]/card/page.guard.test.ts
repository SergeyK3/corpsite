import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("employee card route guard", () => {
  it("compatibility card page redirects via EmployeePersonalCardRedirectClient only", () => {
    const pagePath = resolve(
      process.cwd(),
      "app/directory/personnel/employees/[employeeId]/card/page.tsx",
    );
    const source = readFileSync(pagePath, "utf8");

    expect(source).toContain("EmployeePersonalCardRedirectClient");
    expect(source).not.toContain("PprPersonalCardPageClient");
    expect(source).not.toContain("EmployeeImportCard2PageClient");
    expect(source).not.toContain("EmployeeCardRouteClient");
    expect(source).not.toContain("isPprCardEnabled");
  });

  it("legacy import-card remains on dedicated rollback route", () => {
    const pagePath = resolve(
      process.cwd(),
      "app/directory/personnel/employees/[employeeId]/import-card/page.tsx",
    );
    const source = readFileSync(pagePath, "utf8");

    expect(source).toContain("EmployeeImportCard2PageClient");
  });
});
