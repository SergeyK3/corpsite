import { describe, expect, it } from "vitest";

import {
  formatVisibleRecordsFormula,
  VISIBLE_RECORDS_HELP,
  VISIBLE_RECORDS_LABEL,
} from "./monthlyDiffVisibility";

describe("monthlyDiffVisibility", () => {
  it("documents visible records as review workload, not baseline size", () => {
    expect(VISIBLE_RECORDS_LABEL).toContain("Требуют внимания");
    expect(VISIBLE_RECORDS_HELP).toContain("формируемого эталона");
  });

  it("formats visible records formula from diff buckets", () => {
    expect(
      formatVisibleRecordsFormula({
        newCount: 10,
        changedCount: 5,
        conflictCount: 1,
        pendingRemovals: 2,
      }),
    ).toBe("10 NEW + 5 CHANGED + 1 CONFLICT + 2 REMOVED (без решения)");
  });
});
