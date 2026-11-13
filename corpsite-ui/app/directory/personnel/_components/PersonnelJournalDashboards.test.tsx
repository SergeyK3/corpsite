import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { getPersonnelHeadcountTrend } from "../_lib/personnelReportsApi.client";
import PersonnelJournalDashboards from "./PersonnelJournalDashboards";

vi.mock("../_lib/personnelReportsApi.client", () => ({ getPersonnelHeadcountTrend: vi.fn() }));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("shows actual values above points, gaps for missing months, and no future months", async () => {
  vi.mocked(getPersonnelHeadcountTrend).mockResolvedValue({
    report_code: "personnel_headcount_trend",
    year: 2026,
    as_of: "2026-03-13",
    history_complete: false,
    months: [
      { month: 1, date: "2026-01-31", count: null, source: null, is_current: false },
      { month: 2, date: "2026-02-28", count: 500, source: "approved_employee_events", is_current: false },
      { month: 3, date: "2026-03-13", count: 601, source: "active_register", is_current: true },
    ],
  });

  render(<PersonnelJournalDashboards />);

  expect(await screen.findByTestId("headcount-value-3")).toHaveTextContent("601");
  expect(screen.getByTestId("headcount-value-2")).toHaveTextContent("500");
  expect(screen.getByTestId("headcount-no-data-1")).toHaveTextContent("Нет данных");
  expect(screen.getByText("на сегодня")).toBeInTheDocument();
  expect(screen.queryByText("Апрель")).not.toBeInTheDocument();
});
