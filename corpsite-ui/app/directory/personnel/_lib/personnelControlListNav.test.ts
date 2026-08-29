import { describe, expect, it } from "vitest";

import {
  isPersonnelControlListPath,
  parsePersonnelImportBatchId,
  resolvePersonnelControlListSection,
} from "./personnelControlListNav";

describe("personnelControlListNav", () => {
  it("classifies control-list and unrelated routes", () => {
    expect(isPersonnelControlListPath("/directory/personnel/import/148/review")).toBe(true);
    expect(isPersonnelControlListPath("/directory/personnel/hr-change-events")).toBe(true);
    expect(isPersonnelControlListPath("/directory/personnel/reports")).toBe(false);
  });

  it("keeps existing nested route semantics", () => {
    expect(resolvePersonnelControlListSection("/directory/personnel/import/upload")).toBe("upload");
    expect(resolvePersonnelControlListSection("/directory/personnel/import/148/rows/19")).toBe("analytics");
    expect(resolvePersonnelControlListSection("/directory/personnel/import/review/19")).toBe("review");
    expect(resolvePersonnelControlListSection("/directory/personnel/import/148/review/19")).toBe("medical");
    expect(resolvePersonnelControlListSection("/directory/personnel/monthly-references/7")).toBe("upload");
  });

  it("extracts only a valid batch id", () => {
    expect(parsePersonnelImportBatchId("/directory/personnel/import/148/review")).toBe(148);
    expect(parsePersonnelImportBatchId("/directory/personnel/import/review")).toBeNull();
  });
});
