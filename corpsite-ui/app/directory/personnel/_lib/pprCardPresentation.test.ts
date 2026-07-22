import { describe, expect, it } from "vitest";

import { educationKindLabel, formatPprDate } from "./pprCardPresentation";

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

describe("formatPprDate", () => {
  it("formats full dates as DD.MM.YYYY when day precision is explicit", () => {
    expect(formatPprDate("1990-05-20", "day")).toBe("20.05.1990");
    expect(formatPprDate("2020-01-01", "day")).toBe("01.01.2020");
  });

  it("formats year fields as YYYY when year precision is explicit", () => {
    expect(formatPprDate("2018-01-01", "year")).toBe("2018");
    expect(formatPprDate("2018", "year")).toBe("2018");
  });

  it("formats month fields as MM.YYYY when month precision is explicit", () => {
    expect(formatPprDate("2026-06-01", "month")).toBe("06.2026");
  });
});
