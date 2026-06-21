// FILE: corpsite-ui/app/admin/system/_lib/userLinkageOperationsLabels.test.ts
import { describe, expect, it } from "vitest";

import { diagnosisTone, operationLabel, runStatusClass } from "./userLinkageOperationsLabels";

describe("userLinkageOperationsLabels", () => {
  it("maps operation codes to labels", () => {
    expect(operationLabel("USER_LINKAGE_MANUAL_LINK")).toBe("Manual Link");
    expect(operationLabel("UNKNOWN_OP")).toBe("UNKNOWN_OP");
  });

  it("assigns diagnosis tone colors", () => {
    expect(diagnosisTone("LINK_OK")).toBe("green");
    expect(diagnosisTone("REVIEW_REQUIRED")).toBe("yellow");
    expect(diagnosisTone("MANUAL_DECISION")).toBe("orange");
    expect(diagnosisTone("CONFLICT_REQUIRES_MANUAL_DECISION")).toBe("red");
    expect(diagnosisTone("NO_CANDIDATE_FOUND")).toBe("muted");
  });

  it("returns status badge classes", () => {
    expect(runStatusClass("completed")).toContain("emerald");
    expect(runStatusClass("failed")).toContain("rose");
  });
});
