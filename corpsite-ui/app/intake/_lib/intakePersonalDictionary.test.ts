import { describe, expect, it } from "vitest";

import {
  INTAKE_CITIZENSHIP_CATALOG,
  INTAKE_CITIZENSHIP_POPULAR,
  INTAKE_DICTIONARY_RESULT_LIMIT,
  INTAKE_NATIONALITY_CATALOG,
  INTAKE_NATIONALITY_POPULAR,
  filterIntakeDictionaryOptions,
  isIntakeDictionaryValue,
} from "./intakePersonalDictionary";

describe("intakePersonalDictionary", () => {
  it("shows Kazakhstan first for empty citizenship search", () => {
    const options = filterIntakeDictionaryOptions(
      INTAKE_CITIZENSHIP_CATALOG,
      INTAKE_CITIZENSHIP_POPULAR,
      "",
    );
    expect(options[0]).toBe("Казахстан");
  });

  it("shows kazakhs first for empty nationality search", () => {
    const options = filterIntakeDictionaryOptions(
      INTAKE_NATIONALITY_CATALOG,
      INTAKE_NATIONALITY_POPULAR,
      "",
    );
    expect(options[0]).toBe("казахи");
  });

  it('finds "казахи" when typing "каз"', () => {
    const options = filterIntakeDictionaryOptions(
      INTAKE_NATIONALITY_CATALOG,
      INTAKE_NATIONALITY_POPULAR,
      "каз",
    );
    expect(options).toContain("казахи");
  });

  it('finds "русские" when typing "рус"', () => {
    const options = filterIntakeDictionaryOptions(
      INTAKE_NATIONALITY_CATALOG,
      INTAKE_NATIONALITY_POPULAR,
      "рус",
    );
    expect(options).toContain("русские");
  });

  it('finds Kyrgyz entries when typing "кыр"', () => {
    const citizenship = filterIntakeDictionaryOptions(
      INTAKE_CITIZENSHIP_CATALOG,
      INTAKE_CITIZENSHIP_POPULAR,
      "кыр",
    );
    const nationality = filterIntakeDictionaryOptions(
      INTAKE_NATIONALITY_CATALOG,
      INTAKE_NATIONALITY_POPULAR,
      "кыр",
    );

    expect(citizenship).toContain("Кыргызстан");
    expect(nationality).toContain("кыргызы");
  });

  it("returns no more than 15 options", () => {
    const citizenship = filterIntakeDictionaryOptions(
      INTAKE_CITIZENSHIP_CATALOG,
      INTAKE_CITIZENSHIP_POPULAR,
      "",
      INTAKE_DICTIONARY_RESULT_LIMIT,
    );
    const nationality = filterIntakeDictionaryOptions(
      INTAKE_NATIONALITY_CATALOG,
      INTAKE_NATIONALITY_POPULAR,
      "а",
      INTAKE_DICTIONARY_RESULT_LIMIT,
    );

    expect(citizenship.length).toBeLessThanOrEqual(15);
    expect(nationality.length).toBeLessThanOrEqual(15);
  });

  it("keeps legacy singular nationality values valid in catalog", () => {
    expect(isIntakeDictionaryValue("казах", INTAKE_NATIONALITY_CATALOG)).toBe(true);
  });
});
