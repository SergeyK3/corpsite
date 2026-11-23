import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import PersonnelLkSectionPageClient from "./PersonnelLkSectionPageClient";
import type { MeInfo } from "@/lib/types";

let params = new URLSearchParams();
let currentUser: MeInfo | null = { role_code: "HR_HEAD", has_personnel_files_review: true };
vi.mock("next/navigation", () => ({ useSearchParams: () => params }));
vi.mock("@/lib/currentUser", () => ({ useCurrentUser: () => currentUser }));
vi.mock("./PersonnelLkPageClient", () => ({ default: () => <div data-testid="cards-list">Реестр личных карточек</div> }));
vi.mock("./PersonnelSummaryPageClient", () => ({ default: () => <div data-testid="reports">Отчёты</div> }));

afterEach(() => { cleanup(); params = new URLSearchParams(); currentUser = { role_code: "HR_HEAD", has_personnel_files_review: true }; });

it("opens the existing card list by default", () => {
  render(<PersonnelLkSectionPageClient />);
  expect(screen.getByTestId("cards-list")).toBeInTheDocument();
  expect(screen.queryByTestId("reports")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Отчёты" })).toHaveAttribute("href", "/directory/personnel/lk?view=reports&report=cards");
  expect(Array.from(screen.getByRole("navigation", { name: "Личные карточки" }).querySelectorAll("a"), (link) => link.textContent)).toEqual(["Список карточек", "Проверка карточек", "Отчёты"]);
});

it("opens reports at the new card section URL", () => {
  params = new URLSearchParams("view=reports&report=cards");
  render(<PersonnelLkSectionPageClient />);
  expect(screen.getByTestId("reports")).toBeInTheDocument();
  expect(screen.queryByTestId("cards-list")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Список карточек" })).toHaveAttribute("href", "/directory/personnel/lk");
  expect(screen.getByRole("link", { name: "Отчёты" })).toHaveAttribute("aria-current", "page");
});
