import { describe, expect, it } from "vitest";

import {
  buildItemPayload,
  emptyItemPayloadDraft,
  itemPayloadDraftFromRecord,
} from "./personnelOrderPayload";
import {
  canApplyPersonnelOrder,
  canApplyPersonnelOrderAction,
  canRegisterPersonnelOrder,
  formatPersonnelOrderNumber,
  isEditablePersonnelOrderStatus,
  isPersonnelOrderApplied,
} from "./personnelOrderLabels";

describe("personnelOrderPayload", () => {
  it("builds HIRE payload from draft fields", () => {
    const draft = emptyItemPayloadDraft();
    draft.org_unit_id = "12";
    draft.position_id = "34";
    draft.employment_rate = "1.0";
    expect(buildItemPayload("HIRE", draft)).toEqual({
      org_unit_id: 12,
      position_id: 34,
      employment_rate: 1,
    });
  });

  it("round-trips payload draft for TRANSFER", () => {
    const draft = itemPayloadDraftFromRecord({
      to_org_unit_id: 5,
      to_position_id: 8,
      to_rate: 0.75,
    });
    expect(buildItemPayload("TRANSFER", draft)).toEqual({
      to_org_unit_id: 5,
      to_position_id: 8,
      to_rate: 0.75,
    });
  });
});

describe("personnelOrderLabels helpers", () => {
  it("formats missing order number", () => {
    expect(formatPersonnelOrderNumber(null)).toBe("без номера");
    expect(formatPersonnelOrderNumber("12-К")).toBe("12-К");
  });

  it("exposes lifecycle capability helpers", () => {
    expect(isEditablePersonnelOrderStatus("DRAFT")).toBe(true);
    expect(isEditablePersonnelOrderStatus("READY_FOR_SIGNATURE")).toBe(false);
    expect(isEditablePersonnelOrderStatus("REGISTERED")).toBe(false);
    expect(canRegisterPersonnelOrder("READY_FOR_SIGNATURE")).toBe(true);
    expect(canApplyPersonnelOrder("REGISTERED")).toBe(true);
    expect(canApplyPersonnelOrder("DRAFT")).toBe(false);
    expect(isPersonnelOrderApplied(0)).toBe(false);
    expect(isPersonnelOrderApplied(2)).toBe(true);
    expect(canApplyPersonnelOrderAction("REGISTERED", 0)).toBe(true);
    expect(canApplyPersonnelOrderAction("REGISTERED", 1)).toBe(false);
    expect(canApplyPersonnelOrderAction("SIGNED", 0)).toBe(true);
    expect(canApplyPersonnelOrderAction("DRAFT", 0)).toBe(false);
  });
});
