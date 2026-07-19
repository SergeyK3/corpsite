import { describe, expect, it } from "vitest";

import { buildMrdWorkspaceHref } from "./mrdWorkspaceNavigation";

describe("mrdWorkspaceNavigation", () => {
  it("builds workspace href by mrd id", () => {
    expect(buildMrdWorkspaceHref(42)).toBe("/directory/personnel/monthly-references/42");
  });
});
