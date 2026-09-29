import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("PersonnelOrderDetailDrawer template application placement", () => {
  it("places template application before the editorial editor in the data tab", () => {
    const source = readFileSync(resolve(__dirname, "PersonnelOrderDetailDrawer.tsx"), "utf8");
    const templateIndex = source.indexOf("<PersonnelOrderTemplateApplication");
    const editorialIndex = source.indexOf("<PersonnelOrderEditorialTextEditor");
    expect(templateIndex).toBeGreaterThan(-1);
    expect(editorialIndex).toBeGreaterThan(templateIndex);
  });
});
