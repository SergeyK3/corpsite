import { describe, expect, it } from "vitest";

import { displayForeignLanguageLevel } from "./foreignLanguageDisplay";

describe("displayForeignLanguageLevel", () => {
  it("localizes legacy and canonical proficiency values", () => {
    expect(displayForeignLanguageLevel("dictionary")).toBe("Со словарём");
    expect(displayForeignLanguageLevel("B2")).toBe("Читает и может объясняться");
    expect(displayForeignLanguageLevel("C1")).toBe("Владеет свободно");
    expect(displayForeignLanguageLevel("Владеет свободно")).toBe("Владеет свободно");
  });
});
