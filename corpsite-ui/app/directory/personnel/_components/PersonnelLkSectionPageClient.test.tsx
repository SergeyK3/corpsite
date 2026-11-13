import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import PersonnelLkSectionPageClient from "./PersonnelLkSectionPageClient";

let params = new URLSearchParams();
vi.mock("next/navigation", () => ({ useSearchParams: () => params }));
vi.mock("./PersonnelLkPageClient", () => ({ default: () => <div data-testid="cards-list">Реестр личных карточек</div> }));
vi.mock("./PersonnelSummaryPageClient", () => ({ default: () => <div data-testid="reports">Отчёты</div> }));

afterEach(() => { cleanup(); params = new URLSearchParams(); });

it("opens the existing card list by default", () => {
  render(<PersonnelLkSectionPageClient />);
  expect(screen.getByTestId("cards-list")).toBeInTheDocument();
  expect(screen.queryByTestId("reports")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Отчёты" })).toHaveAttribute("href", "/directory/personnel/lk?view=reports&report=cards");
});

it("opens reports at the new card section URL", () => {
  params = new URLSearchParams("view=reports&report=cards");
  render(<PersonnelLkSectionPageClient />);
  expect(screen.getByTestId("reports")).toBeInTheDocument();
  expect(screen.queryByTestId("cards-list")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Список карточек" })).toHaveAttribute("href", "/directory/personnel/lk");
});
