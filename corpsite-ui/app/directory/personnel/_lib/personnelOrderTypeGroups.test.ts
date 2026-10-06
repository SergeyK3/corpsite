import { describe, expect, it } from "vitest";
import { PERSONNEL_ORDER_CREATE_TYPES } from "./personnelOrderLabels";
import { PERSONNEL_ORDER_GROUPS, personnelOrderGroupTypes, searchPersonnelOrderTypes } from "./personnelOrderTypeGroups";

describe("personnel order display groups", () => {
  it("keeps every existing creation code exactly once without introducing actions", () => {
    const grouped = PERSONNEL_ORDER_GROUPS.flatMap(group => personnelOrderGroupTypes(group.id));
    expect(PERSONNEL_ORDER_GROUPS).toHaveLength(7);
    expect([...grouped].sort()).toEqual([...PERSONNEL_ORDER_CREATE_TYPES].sort());
    expect(new Set(grouped).size).toBe(grouped.length);
    expect(personnelOrderGroupTypes("employment")).toEqual(["HIRE", "TRANSFER", "TERMINATION"]);
    expect(personnelOrderGroupTypes("parenthood")).toEqual(["RETURN_FROM_CHILDCARE_LEAVE", "LEAVE.CHILDCARE.GRANT"]);
    expect(personnelOrderGroupTypes("other_leave")).toEqual([]);
    expect(personnelOrderGroupTypes("record_changes")).toEqual([]);
  });

  it("searches approved Russian and Kazakh names regardless of the display language", () => {
    expect(searchPersonnelOrderTypes("  ТРУДОВ  ")).toEqual(["LEAVE.ANNUAL.GRANT"]);
    expect(searchPersonnelOrderTypes("еңбек демалысы")).toContain("LEAVE.ANNUAL.GRANT");
    expect(searchPersonnelOrderTypes("ребенком")).toEqual(["RETURN_FROM_CHILDCARE_LEAVE", "LEAVE.CHILDCARE.GRANT"]);
    expect(searchPersonnelOrderTypes("жалақы сақталмайтын")).toEqual(["LEAVE.UNPAID.GRANT", "LEAVE.CHILDCARE.GRANT"]);
    expect(searchPersonnelOrderTypes("несуществующий вид")).toEqual([]);
  });
});
