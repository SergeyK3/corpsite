import { describe, expect, it } from "vitest";

import {
  isValidMilitarySpecialtyCode,
  militarySpecialtyCodeValidationMessage,
  sanitizeMilitarySpecialtyCodeInput,
} from "./militarySpecialtyCode";

describe("militarySpecialtyCode", () => {
  it("keeps only digits and limits length to seven", () => {
    expect(sanitizeMilitarySpecialtyCodeInput("868123А")).toBe("868123");
    expect(sanitizeMilitarySpecialtyCodeInput("12-34 567 890")).toBe("1234567");
    expect(sanitizeMilitarySpecialtyCodeInput("abc")).toBe("");
  });

  it("accepts empty or exactly seven digits", () => {
    expect(isValidMilitarySpecialtyCode("")).toBe(true);
    expect(isValidMilitarySpecialtyCode("1234567")).toBe(true);
    expect(isValidMilitarySpecialtyCode("123456")).toBe(false);
    expect(isValidMilitarySpecialtyCode("12345678")).toBe(false);
    expect(isValidMilitarySpecialtyCode("123456A")).toBe(false);
  });

  it("returns validation message for invalid values", () => {
    expect(militarySpecialtyCodeValidationMessage("123456")).toBe(
      "Номер ВУС должен содержать ровно 7 цифр.",
    );
    expect(militarySpecialtyCodeValidationMessage("1234567")).toBeNull();
  });
});
