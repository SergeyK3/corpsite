import { describe, expect, it } from "vitest";

import {
  buildLegacyRegularTaskTemplatesHref,
  buildTemplateSectionHref,
  resolveTemplateSection,
} from "./templateSections";

describe("template section routing", () => {
  it("defaults unknown sections to tasks", () => {
    expect(resolveTemplateSection(null)).toBe("tasks");
    expect(resolveTemplateSection("unknown")).toBe("tasks");
  });

  it("builds canonical section URLs without discarding unrelated query parameters", () => {
    expect(buildTemplateSectionHref("personnel-orders", new URLSearchParams("q=monthly&section=tasks"))).toBe(
      "/admin/templates?q=monthly&section=personnel-orders",
    );
  });

  it("redirects legacy routes to task templates and preserves their query parameters", () => {
    expect(
      buildLegacyRegularTaskTemplatesHref({ q: "monthly", owner: ["12", "18"], section: "runs" }),
    ).toBe("/admin/templates?q=monthly&owner=12&owner=18&section=tasks");
  });
});
