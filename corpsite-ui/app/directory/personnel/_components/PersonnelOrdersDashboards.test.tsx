import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { getPersonnelOrdersMonthlyDashboard } from "../_lib/personnelReportsApi.client";
import PersonnelOrdersDashboards from "./PersonnelOrdersDashboards";

vi.mock("../_lib/personnelReportsApi.client", () => ({ getPersonnelOrdersMonthlyDashboard: vi.fn() }));

afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("shows a visible value above every point, including zero, and labels the current month", async () => {
  vi.mocked(getPersonnelOrdersMonthlyDashboard).mockResolvedValue({
    report_code: "personnel_orders_monthly_dashboard",
    year: 2026,
    as_of: "2026-03-13",
    order_type: null,
    months: [
      { month: 1, count: 8, is_current: false },
      { month: 2, count: 3, is_current: false },
      { month: 3, count: 0, is_current: true },
    ],
    total: 11,
  });

  render(<PersonnelOrdersDashboards />);

  const currentValue = await screen.findByTestId("orders-month-count-3");
  expect(currentValue).toHaveTextContent("0");
  expect(screen.getByTestId("orders-month-count-1")).toHaveTextContent("8");
  expect(screen.getByTestId("orders-month-count-2")).toHaveTextContent("3");
  expect(currentValue.getAttribute("y")).toBeTruthy();
  expect(Number(currentValue.getAttribute("y"))).toBeLessThan(
    Number(currentValue.parentElement?.querySelector("circle")?.getAttribute("cy")),
  );
  expect(screen.getByText("по сегодня")).toBeInTheDocument();
  expect(screen.queryByText("Апрель")).not.toBeInTheDocument();
});

it("requests a new server aggregation for each selected type", async () => {
  vi.mocked(getPersonnelOrdersMonthlyDashboard).mockImplementation(async (orderType) => ({
    report_code: "personnel_orders_monthly_dashboard",
    year: 2026,
    as_of: "2026-03-13",
    order_type: orderType || null,
    months: [{ month: 3, count: orderType === "TRANSFER" ? 2 : 8, is_current: true }],
    total: orderType === "TRANSFER" ? 2 : 8,
  }));

  render(<PersonnelOrdersDashboards />);
  expect(await screen.findByTestId("orders-month-count-3")).toHaveTextContent("8");
  expect(getPersonnelOrdersMonthlyDashboard).toHaveBeenCalledWith(null);

  fireEvent.change(screen.getByLabelText("Тип приказа"), { target: { value: "TRANSFER" } });
  await waitFor(() => expect(getPersonnelOrdersMonthlyDashboard).toHaveBeenCalledWith("TRANSFER"));
  expect(await screen.findByTestId("orders-month-count-3")).toHaveTextContent("2");

  fireEvent.change(screen.getByLabelText("Тип приказа"), { target: { value: "" } });
  await waitFor(() => expect(getPersonnelOrdersMonthlyDashboard).toHaveBeenLastCalledWith(null));
  expect(await screen.findByTestId("orders-month-count-3")).toHaveTextContent("8");
});
