import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { PPR_CARD_SECTIONS } from "@/lib/pprCardSections";
import { isPprDisplayValue } from "../_lib/pprCardPresentation";
import {
  PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE,
  PPR_MILITARY_RECORD_KIND_REGISTRATION,
} from "../_lib/pprQueryTypes";

describe("PPR military architecture guards (WP-PR-031)", () => {
  it("section registry includes military between family and employment biography", () => {
    const ids = PPR_CARD_SECTIONS.map((section) => section.id);
    expect(ids).toContain("military");
    expect(ids.indexOf("family")).toBeLessThan(ids.indexOf("military"));
    expect(ids.indexOf("military")).toBeLessThan(ids.indexOf("employment_biography"));
  });

  it("personal card page wires military section component", () => {
    const pagePath = resolve(
      process.cwd(),
      "app/directory/personnel/_components/PprPersonalCardPageClient.tsx",
    );
    const source = readFileSync(pagePath, "utf8");
    expect(source).toContain("PprCardMilitarySection");
    expect(source).toContain('id="military"');
    expect(source).toContain("Воинский учёт");
    expect(source).toContain("PPR_SECTION_CODE_MILITARY");
  });

  it("military command client exposes person and employee routes", () => {
    const apiPath = resolve(
      process.cwd(),
      "app/directory/personnel/_lib/pprCommandApi.client.ts",
    );
    const source = readFileSync(apiPath, "utf8");
    expect(source).toContain("/military-service/records");
    expect(source).toContain("createMilitaryServiceByPerson");
    expect(source).toContain("createMilitaryServiceByEmployee");
    expect(source).toContain("voidMilitaryServiceByPerson");
    expect(source).toContain("supersedeMilitaryServiceByEmployee");
    expect(source).not.toContain("updateMilitary");
  });

  it("display helper hides empty values and redaction placeholders", () => {
    expect(isPprDisplayValue(null)).toBe(false);
    expect(isPprDisplayValue("")).toBe(false);
    expect(isPprDisplayValue("   ")).toBe(false);
    expect(isPprDisplayValue("***")).toBe(false);
    expect(isPprDisplayValue("рядовой")).toBe(true);
  });

  it("demo seed record kinds use canonical codes not UI labels", () => {
    expect(PPR_MILITARY_RECORD_KIND_REGISTRATION).toBe("registration");
    expect(PPR_MILITARY_RECORD_KIND_NOT_APPLICABLE).toBe("not_applicable");
  });
});
