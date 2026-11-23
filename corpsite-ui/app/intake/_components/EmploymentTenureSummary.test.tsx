import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import EmploymentTenureSummary from "./EmploymentTenureSummary";
import type { EmploymentTenureCalculation } from "../_lib/employmentTenureApi.client";

afterEach(() => {
  cleanup();
});

const sampleCalculation: EmploymentTenureCalculation = {
  calculation_date: "2026-07-23",
  arithmetic_sum_days: 12442,
  overlap_excluded_days: 4737,
  total_days: 7705,
  total_decimal_years: 21.1,
  total_ymd: { years: 21, months: 1, days: 5 },
  records: [
    {
      record_id: "r1",
      index: 0,
      label: "R1",
      days: 1171,
      included: true,
      is_open_ended: false,
      overlaps_other: true,
      warning: null,
    },
    {
      record_id: "broken",
      index: 1,
      label: "Broken",
      days: null,
      included: false,
      is_open_ended: false,
      overlaps_other: false,
      warning: "Не указана дата начала — запись не включена в общий стаж",
    },
  ],
};

describe("EmploymentTenureSummary", () => {
  it("shows total tenure and calculation date", () => {
    render(
      <EmploymentTenureSummary
        items={[
          {
            organization: "R1",
            position: "",
            year_from: "2005-06-18",
            year_to: "2008-09-01",
            reason_for_leaving: "",
          },
        ]}
        calculation={sampleCalculation}
      />,
    );

    expect(screen.getByTestId("intake-employment-total-tenure")).toHaveTextContent("21,10 года (7 705 дней)");
    expect(screen.getByTestId("intake-employment-tenure-calc-date")).toHaveTextContent("23.07.2026");
  });

  it("shows compact excluded summary without duplicating row warnings", () => {
    render(
      <EmploymentTenureSummary
        items={[
          {
            organization: "R1",
            position: "",
            year_from: "2005-06-18",
            year_to: "2008-09-01",
            reason_for_leaving: "",
          },
          {
            organization: "Broken",
            position: "",
            year_from: "",
            year_to: "",
            reason_for_leaving: "",
          },
        ]}
        calculation={sampleCalculation}
      />,
    );

    expect(screen.getByTestId("intake-employment-tenure-excluded-toggle")).toHaveTextContent(
      "Не включено записей: 1",
    );
    expect(screen.queryByTestId("intake-employment-tenure-warnings")).not.toBeInTheDocument();
  });
});
