import { fireEvent, render, screen, waitFor, cleanup } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import PersonnelQualificationCategoriesSectionPageClient from "./PersonnelQualificationCategoriesSectionPageClient";

const fetchReport = vi.hoisted(() => vi.fn());
let params = new URLSearchParams();
vi.mock("@/lib/api", () => ({ apiFetchJson: fetchReport }));
vi.mock("next/navigation", () => ({ useSearchParams: () => params }));
vi.mock("./PersonnelQualificationCategoriesReport", () => ({
  default: ({ report, unitId, onUnitIdChange }: { report: unknown; unitId: string; onUnitIdChange: (value: string) => void }) =>
    <div data-testid="category-list"><span data-testid="list-unit">{unitId}</span><span data-testid="list-loaded">{report ? "yes" : "no"}</span><button onClick={() => onUnitIdChange("2")}>Отделение 2</button></div>,
}));
vi.mock("./PersonnelQualificationCategoriesSummary", () => ({
  default: ({ report, unitId }: { report: unknown; unitId: string }) =>
    <div data-testid="category-summary"><span data-testid="summary-unit">{unitId}</span><span data-testid="summary-loaded">{report ? "yes" : "no"}</span></div>,
}));

afterEach(() => { cleanup(); fetchReport.mockReset(); params = new URLSearchParams(); });

it("opens the list by default and shares one API selection and department with reports", async () => {
  fetchReport.mockResolvedValue({ as_of_date: "2026-11-12", employees: [] });
  const view = render(<PersonnelQualificationCategoriesSectionPageClient />);
  expect(screen.getByTestId("category-list")).toBeInTheDocument();
  expect(screen.queryByTestId("category-summary")).not.toBeInTheDocument();
  await waitFor(() => expect(screen.getByTestId("list-loaded")).toHaveTextContent("yes"));
  expect(fetchReport).toHaveBeenCalledTimes(1);
  expect(fetchReport).toHaveBeenCalledWith("/directory/personnel/reports/qualification-categories");
  fireEvent.click(screen.getByRole("button", { name: "Отделение 2" }));
  params = new URLSearchParams("view=reports");
  view.rerender(<PersonnelQualificationCategoriesSectionPageClient />);
  expect(screen.getByTestId("category-summary")).toBeInTheDocument();
  expect(screen.getByTestId("summary-unit")).toHaveTextContent("2");
  expect(screen.getByTestId("summary-loaded")).toHaveTextContent("yes");
  expect(fetchReport).toHaveBeenCalledTimes(1);
});
