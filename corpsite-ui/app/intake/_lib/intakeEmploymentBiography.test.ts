import { describe, expect, it } from "vitest";

import {
  emptyIntakeEmploymentBiographyEntry,
  formatIntakeEmploymentPeriodCell,
  sortIntakeEmploymentBiographyRows,
} from "./intakeEmploymentBiography";

describe("intakeEmploymentBiography", () => {
  it("sorts employment rows by start date with newest first", () => {
    const rows = sortIntakeEmploymentBiographyRows([
      {
        ...emptyIntakeEmploymentBiographyEntry(),
        organization: "Old",
        year_from: "2018-09-01",
      },
      {
        ...emptyIntakeEmploymentBiographyEntry(),
        organization: "New",
        year_from: "2022-06-15",
      },
    ]);

    expect(rows.map(({ item }) => item.organization)).toEqual(["New", "Old"]);
  });

  it("formats current employment period without end date", () => {
    expect(formatIntakeEmploymentPeriodCell("2018-09-01", "")).toBe("01.09.2018 — наст. время");
  });

  it("formats completed employment period range", () => {
    expect(formatIntakeEmploymentPeriodCell("2018-09-01", "2022-06-15")).toBe(
      "01.09.2018 — 15.06.2022",
    );
  });
});
