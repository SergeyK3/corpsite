import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("person card route guard", () => {
  it("card page renders canonical PPR client by person_id", () => {
    const pagePath = resolve(
      process.cwd(),
      "app/directory/personnel/persons/[personId]/card/page.tsx",
    );
    const source = readFileSync(pagePath, "utf8");

    expect(source).toContain("PprPersonalCardPageClient");
    expect(source).toContain("personId={personId}");
    expect(source).not.toContain("employeeId");
    expect(source).not.toContain("EmployeeImportCard2PageClient");
  });
});
