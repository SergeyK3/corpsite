import { describe, expect, it } from "vitest";

import { buildItemPayload, itemPayloadDraftFromRecord } from "./personnelOrderPayload";

describe("termination reason payload", () => {
  it("preserves the controlled reason after loading an existing item", () => {
    const draft = itemPayloadDraftFromRecord({ termination_reason: "EMPLOYEE_INITIATIVE" });
    expect(draft.termination_reason).toBe("EMPLOYEE_INITIATIVE");
    expect(buildItemPayload("TERMINATION", draft)).toEqual({ termination_reason: "EMPLOYEE_INITIATIVE" });
  });
});
