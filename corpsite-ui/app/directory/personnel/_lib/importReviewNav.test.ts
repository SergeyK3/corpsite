import { describe, expect, it } from "vitest";

import {
  buildImportReviewModeHref,
  isImportReviewModeNavActive,
  parseImportReviewMode,
} from "./importReviewNav";

describe("importReviewNav", () => {
  it("routes removed review modes to the remaining personnel mode", () => {
    expect(parseImportReviewMode("declaration")).toBe("personnel");
    expect(parseImportReviewMode("technical")).toBe("personnel");
    expect(parseImportReviewMode(null)).toBe("personnel");
  });

  it("builds review mode href", () => {
    expect(buildImportReviewModeHref(148, "personnel")).toBe(
      "/directory/personnel/import/148/review?mode=personnel",
    );
  });

  it("detects active review mode tab only on review list route", () => {
    const sp = new URLSearchParams("mode=declaration");
    expect(
      isImportReviewModeNavActive(
        "/directory/personnel/import/148/review",
        "personnel",
        148,
        sp,
      ),
    ).toBe(true);
    expect(
      isImportReviewModeNavActive(
        "/directory/personnel/import/148/review/42",
        "personnel",
        148,
        sp,
      ),
    ).toBe(false);
  });
});
