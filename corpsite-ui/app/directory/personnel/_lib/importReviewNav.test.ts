import { describe, expect, it } from "vitest";

import {
  buildImportReviewModeHref,
  isImportReviewModeNavActive,
  parseImportReviewMode,
} from "./importReviewNav";

describe("importReviewNav", () => {
  it("parses review mode from search params", () => {
    expect(parseImportReviewMode("declaration")).toBe("declaration");
    expect(parseImportReviewMode("technical")).toBe("technical");
    expect(parseImportReviewMode(null)).toBe("personnel");
  });

  it("builds review mode href", () => {
    expect(buildImportReviewModeHref(148, "declaration")).toBe(
      "/directory/personnel/import/148/review?mode=declaration",
    );
  });

  it("detects active review mode tab only on review list route", () => {
    const sp = new URLSearchParams("mode=declaration");
    expect(
      isImportReviewModeNavActive(
        "/directory/personnel/import/148/review",
        "declaration",
        148,
        sp,
      ),
    ).toBe(true);
    expect(
      isImportReviewModeNavActive(
        "/directory/personnel/import/148/review",
        "personnel",
        148,
        sp,
      ),
    ).toBe(false);
    expect(
      isImportReviewModeNavActive(
        "/directory/personnel/import/148/review/42",
        "declaration",
        148,
        sp,
      ),
    ).toBe(false);
  });
});
