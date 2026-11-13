import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { CurrentUserProvider } from "@/lib/currentUser";
import PersonnelJournalSectionPageClient from "./PersonnelJournalSectionPageClient";

const replace = vi.fn();
let params = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => params,
}));
vi.mock("./PersonnelJournalPageClient", () => ({ default: () => <div data-testid="personnel-journal">Прежний журнал</div> }));
vi.mock("./PersonnelTypeHeadcountReport", () => ({
  default: () => <div data-testid="journal-report">Численность работников по типу персонала</div>,
}));
vi.mock("./PersonnelJournalDashboards", () => ({
  default: () => <div data-testid="journal-dashboards">Численность персонала с начала года</div>,
}));

afterEach(() => { cleanup(); replace.mockReset(); params = new URLSearchParams(); });

it("opens the existing journal by default and places the type report in journal reports", () => {
  const view = render(<CurrentUserProvider value={{ has_personnel_admin: true } as any}>
    <PersonnelJournalSectionPageClient />
  </CurrentUserProvider>);
  expect(screen.getByTestId("personnel-journal")).toBeInTheDocument();
  expect(screen.queryByTestId("journal-report")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Отчёты" }));
  expect(replace).toHaveBeenCalledWith("/directory/personnel/journal?view=reports");
  params = new URLSearchParams("view=reports");
  view.rerender(<CurrentUserProvider value={{ has_personnel_admin: true } as any}>
    <PersonnelJournalSectionPageClient />
  </CurrentUserProvider>);
  expect(screen.getByTestId("journal-report")).toHaveTextContent("Численность работников по типу персонала");
  expect(screen.queryByTestId("personnel-journal")).not.toBeInTheDocument();
});

it("keeps the report unavailable to journal-only readers", () => {
  params = new URLSearchParams("view=reports");
  render(<CurrentUserProvider value={{ has_personnel_events_read: true } as any}>
    <PersonnelJournalSectionPageClient />
  </CurrentUserProvider>);
  expect(screen.getByTestId("personnel-journal")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Отчёты" })).not.toBeInTheDocument();
  expect(screen.queryByTestId("journal-report")).not.toBeInTheDocument();
});

it("opens dashboards after reports without changing the default journal", () => {
  const view = render(<CurrentUserProvider value={{ has_personnel_admin: true } as any}>
    <PersonnelJournalSectionPageClient />
  </CurrentUserProvider>);
  expect(screen.getAllByRole("button").map((button) => button.textContent)).toEqual(["Журнал", "Отчёты", "Дашборды"]);
  expect(screen.getByTestId("personnel-journal")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Дашборды" }));
  expect(replace).toHaveBeenCalledWith("/directory/personnel/journal?view=dashboards");
  params = new URLSearchParams("view=dashboards");
  view.rerender(<CurrentUserProvider value={{ has_personnel_admin: true } as any}>
    <PersonnelJournalSectionPageClient />
  </CurrentUserProvider>);
  expect(screen.getByTestId("journal-dashboards")).toBeInTheDocument();
  expect(screen.queryByTestId("journal-report")).not.toBeInTheDocument();
});

it("keeps dashboards unavailable to journal-only readers", () => {
  params = new URLSearchParams("view=dashboards");
  render(<CurrentUserProvider value={{ has_personnel_events_read: true } as any}>
    <PersonnelJournalSectionPageClient />
  </CurrentUserProvider>);
  expect(screen.getByTestId("personnel-journal")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Дашборды" })).not.toBeInTheDocument();
});
