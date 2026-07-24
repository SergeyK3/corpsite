import { describe, expect, it } from "vitest";

import {
  deriveIntakeSurnameAlphabet,
  isIntakePersonnelNumberEditable,
  normalizeIntakePersonnelNumber,
  reconcileIntakePersonalBlock,
  shouldShowIntakePersonnelNumberField,
} from "./intakePersonalFields";

describe("intakePersonalFields", () => {
  it("derives alphabet from first surname grapheme", () => {
    expect(deriveIntakeSurnameAlphabet("Иванов")).toBe("И");
    expect(deriveIntakeSurnameAlphabet("  петров ")).toBe("П");
    expect(deriveIntakeSurnameAlphabet("")).toBe("");
  });

  it("normalizes personnel number whitespace", () => {
    expect(normalizeIntakePersonnelNumber("  12345  ")).toBe("12345");
    expect(normalizeIntakePersonnelNumber(null)).toBe("");
  });

  it("shows personnel number for HR always and for public only when assigned", () => {
    expect(shouldShowIntakePersonnelNumberField("hr-on-behalf", "")).toBe(true);
    expect(shouldShowIntakePersonnelNumberField("public", "")).toBe(false);
    expect(shouldShowIntakePersonnelNumberField("public", "A-42")).toBe(true);
  });

  it("allows personnel number edit only for HR on-behalf", () => {
    expect(isIntakePersonnelNumberEditable("hr-on-behalf", false)).toBe(true);
    expect(isIntakePersonnelNumberEditable("hr-on-behalf", true)).toBe(false);
    expect(isIntakePersonnelNumberEditable("public", false)).toBe(false);
  });

  it("reconciles personnel number on load", () => {
    expect(
      reconcileIntakePersonalBlock({
        last_name: "Иванов",
        first_name: "Иван",
        middle_name: "",
        birth_date: "",
        birth_place: "",
        gender: "",
        citizenship: "",
        nationality: "",
        personnel_number: "  77  ",
      }).personnel_number,
    ).toBe("77");
  });
});
