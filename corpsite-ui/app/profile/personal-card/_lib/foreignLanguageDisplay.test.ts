import { describe, expect, it } from "vitest";

import { displayForeignLanguageLevel, foreignLanguageLevelForEditor, FOREIGN_LANGUAGE_LEVELS } from "./foreignLanguageDisplay";

describe("displayForeignLanguageLevel", () => {
  it("localizes legacy and canonical proficiency values", () => {
    expect(displayForeignLanguageLevel("dictionary")).toBe("Со словарём");
    expect(displayForeignLanguageLevel("B2")).toBe("Читает и может объясняться");
    expect(displayForeignLanguageLevel("C1")).toBe("Владеет свободно");
    expect(displayForeignLanguageLevel("Владеет свободно")).toBe("Владеет свободно");
  });

  it("normalizes editor state to every supported proficiency level", () => {
    expect(foreignLanguageLevelForEditor("dictionary")).toBe(FOREIGN_LANGUAGE_LEVELS[0]);
    expect(foreignLanguageLevelForEditor("B2")).toBe(FOREIGN_LANGUAGE_LEVELS[1]);
    expect(foreignLanguageLevelForEditor("C1")).toBe(FOREIGN_LANGUAGE_LEVELS[2]);
    expect(foreignLanguageLevelForEditor("obsolete value")).toBe(FOREIGN_LANGUAGE_LEVELS[0]);
  });
});
