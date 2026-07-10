import { describe, expect, it } from "vitest";

import { emptyItemPayloadDraft } from "./personnelOrderPayload";
import {
  clearOrgDependentFields,
  isOrgScopedItemType,
  selectedOrgUnitIdFromDraft,
  selectedPositionIdFromDraft,
  setOrgUnitAndClearPosition,
  setPositionId,
} from "./personnelOrderOrgScope";
import { filterOrgUnitOptionsForGroup } from "@/lib/taskOrgFilters";

describe("personnelOrderOrgScope cascade", () => {
  it("detects org-scoped item types", () => {
    expect(isOrgScopedItemType("HIRE")).toBe(true);
    expect(isOrgScopedItemType("TRANSFER")).toBe(true);
    expect(isOrgScopedItemType("TERMINATION")).toBe(false);
  });

  it("clears unit and position when group changes for HIRE", () => {
    const draft = {
      ...emptyItemPayloadDraft(),
      org_unit_id: "12",
      position_id: "34",
      employment_rate: "1",
    };
    expect(clearOrgDependentFields(draft, "HIRE")).toEqual({
      ...draft,
      org_unit_id: "",
      position_id: "",
    });
  });

  it("clears to_unit and to_position when group changes for TRANSFER", () => {
    const draft = {
      ...emptyItemPayloadDraft(),
      to_org_unit_id: "12",
      to_position_id: "34",
    };
    expect(clearOrgDependentFields(draft, "TRANSFER")).toEqual({
      ...draft,
      to_org_unit_id: "",
      to_position_id: "",
    });
  });

  it("sets unit and clears position on unit change", () => {
    const hireDraft = {
      ...emptyItemPayloadDraft(),
      org_unit_id: "1",
      position_id: "99",
    };
    expect(setOrgUnitAndClearPosition(hireDraft, "HIRE", 55)).toEqual({
      ...hireDraft,
      org_unit_id: "55",
      position_id: "",
    });

    const transferDraft = {
      ...emptyItemPayloadDraft(),
      to_org_unit_id: "1",
      to_position_id: "99",
    };
    expect(setOrgUnitAndClearPosition(transferDraft, "TRANSFER", null)).toEqual({
      ...transferDraft,
      to_org_unit_id: "",
      to_position_id: "",
    });
  });

  it("reads and writes position by item type", () => {
    const draft = setPositionId(
      setOrgUnitAndClearPosition(emptyItemPayloadDraft(), "HIRE", 7),
      "HIRE",
      "42",
    );
    expect(selectedOrgUnitIdFromDraft(draft, "HIRE")).toBe(7);
    expect(selectedPositionIdFromDraft(draft, "HIRE")).toBe("42");
  });

  it("filters org units by department group", () => {
    const options = [
      { unit_id: 1, name: "A", group_id: 10 },
      { unit_id: 2, name: "B", group_id: 20 },
      { unit_id: 3, name: "C", group_id: 10 },
    ];
    expect(filterOrgUnitOptionsForGroup(options, 10).map((row) => row.unit_id)).toEqual([1, 3]);
    expect(filterOrgUnitOptionsForGroup(options, undefined)).toHaveLength(3);
  });
});
