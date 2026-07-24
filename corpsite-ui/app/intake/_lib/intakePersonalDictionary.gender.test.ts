import { describe, expect, it } from "vitest";

import {
  INTAKE_GENDER_OPTIONS,
  normalizeIntakeGenderValue,
} from "./intakePersonalDictionary";

describe("intake gender dictionary", () => {
  it("offers male and female options", () => {
    expect(INTAKE_GENDER_OPTIONS.map((option) => option.label)).toEqual([
      "Выберите…",
      "Мужской",
      "Женский",
    ]);
  });

  it("normalizes common legacy values", () => {
    expect(normalizeIntakeGenderValue("мужской")).toBe("Мужской");
    expect(normalizeIntakeGenderValue("женский")).toBe("Женский");
    expect(normalizeIntakeGenderValue("Мужской")).toBe("Мужской");
  });
});
