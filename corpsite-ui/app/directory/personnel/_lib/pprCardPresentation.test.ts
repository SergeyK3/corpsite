import { describe, expect, it } from "vitest";

import { educationKindLabel } from "./pprCardPresentation";

describe("educationKindLabel", () => {
  it("maps canonical education_kind codes to Russian labels", () => {
    expect(educationKindLabel("basic")).toBe("Базовое образование");
    expect(educationKindLabel("internship")).toBe("Интернатура");
    expect(educationKindLabel("residency")).toBe("Резидентура");
    expect(educationKindLabel("masters")).toBe("Магистратура");
    expect(educationKindLabel("phd")).toBe("Докторантура");
    expect(educationKindLabel("other")).toBe("Прочее");
  });

  it("falls back to raw value for unknown codes", () => {
    expect(educationKindLabel("custom")).toBe("custom");
  });
});
