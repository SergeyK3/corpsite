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
  it("serializes single-day and continuous unpaid periods in the versioned contract", () => {
    const single = buildItemPayload("LEAVE.UNPAID.GRANT", {
      ...emptyItemPayloadDraft(), leave_start: "2026-07-07", leave_end: "2026-07-07", application_date: "2026-07-01",
    });
    const range = buildItemPayload("LEAVE.UNPAID.GRANT", {
      ...emptyItemPayloadDraft(), leave_start: "2026-07-13", leave_end: "2026-07-15", application_date: "2026-07-01",
    });
    expect(single.leave).toEqual({ period_type: "SINGLE_DAY", start: "2026-07-07", end: "2026-07-07", days: 1 });
    expect(range.leave).toEqual({ period_type: "CONTINUOUS_RANGE", start: "2026-07-13", end: "2026-07-15", days: 3 });
    expect(single).not.toHaveProperty("leave_start");
    expect(range).not.toHaveProperty("leave_end");
  });

  it("preserves confirmed KK document forms when unpaid leave is saved and reopened", () => {
    const payload = buildItemPayload("LEAVE.UNPAID.GRANT", {
      ...emptyItemPayloadDraft(),
      leave_start: "2026-07-07", leave_end: "2026-07-07",
      org_unit_document_genitive_kk: "Сәулелік диагностика бөлімшесінің",
      position_document_possessive_kk: "КТ дәрігері",
      employee_full_name_dative_kk: "Ассель Адиловна Ильясоваға",
      employee_full_name_genitive_kk: "Ассель Адиловна Ильясованың",
    });
    expect(payload.document_forms_kk).toEqual({
      org_unit_document_genitive_kk: "Сәулелік диагностика бөлімшесінің",
      position_document_possessive_kk: "КТ дәрігері",
      employee_full_name_dative_kk: "Ассель Адиловна Ильясоваға",
      employee_full_name_genitive_kk: "Ассель Адиловна Ильясованың",
    });
    expect(itemPayloadDraftFromRecord(payload)).toMatchObject(payload.document_forms_kk as object);
  });

  it("reopens modern and legacy unpaid leave payloads", () => {
    const modern = itemPayloadDraftFromRecord({ leave: { period_type: "SINGLE_DAY", start: "2026-07-07", end: "2026-07-07", days: 1 } });
    expect(modern.leave_start).toBe("2026-07-07");
    expect(modern.leave_end).toBe("2026-07-07");
    const legacy = itemPayloadDraftFromRecord({ leave_start: "2026-07-13", leave_end: "2026-07-15", leave_days: 3 });
    expect(legacy.leave_start).toBe("2026-07-13");
    expect(legacy.leave_end).toBe("2026-07-15");
  });

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
