import { describe, expect, it } from "vitest";

import { resolvePersonnelOrderPositionText } from "./personnelOrderPositionDictionary";
import { renderPersonnelOrderPrintItemText } from "./personnelOrderPrintItemText";

describe("personnel-order position dictionary", () => {
  it("translates only the approved Russian anesthetist-nurse pair to Kazakh", () => {
    expect(resolvePersonnelOrderPositionText({ ru: "Медсестра — анестезистка" }, "kk"))
      .toBe("анестезист мейіргері");
  });

  it("does not replace a saved Kazakh localization", () => {
    expect(resolvePersonnelOrderPositionText({ ru: "медсестра-анестезистка", kk: "сақталған атау" }, "kk"))
      .toBe("сақталған атау");
  });

  it("uses the pair in the printed personnel-order text", () => {
    const text = renderPersonnelOrderPrintItemText({
      itemNumber: 1,
      itemTypeCode: "HIRE",
      employeeName: "Тест",
      effectiveDate: "2026-07-07",
      orgUnitName: { ru: "Отделение" },
      positionName: { ru: "Медсестра-анестезистка" },
      toOrgUnitName: null,
      toPositionName: null,
      rate: 1,
      toRate: null,
      concurrentRate: null,
      remainingRate: null,
      totalRate: null,
      terminationReason: null,
      payload: {},
    }, "kk");
    expect(text.join(" ")).toContain("анестезист мейіргері");
  });
});
