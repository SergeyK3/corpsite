// FILE: corpsite-ui/app/admin/regular-tasks/catch-up/CatchUpRunClient.test.tsx

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { catchUpUiLabel } from "@/lib/i18n";

import CatchUpRunClient from "./CatchUpRunClient";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("@/lib/api", () => ({
  apiFetchJson: vi.fn(async (path: string) => {
    if (path === "/directory/department-groups") return { items: [] };
    if (path === "/directory/roles") return { items: [] };
    if (path === "/regular-tasks") return { items: [] };
    return {};
  }),
  apiCatchUpRegularTasks: vi.fn(),
  apiGetRegularTaskRunItems: vi.fn(async () => ({ items: [] })),
}));

vi.mock("@/lib/orgUnitsSelect", () => ({
  loadOrgUnitSelectOptions: vi.fn(async () => []),
  buildOrgUnitSelectGroups: vi.fn(() => []),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("CatchUpRunClient form layout", () => {
  beforeEach(() => {
    render(<CatchUpRunClient />);
  });

  it("renders periodicity before period field in DOM order", () => {
    const grid = screen.getByTestId("catch-up-form-grid");
    const testIds = within(grid)
      .getAllByRole("combobox")
      .map((el) => el.getAttribute("data-testid"))
      .filter(Boolean);

    expect(testIds.indexOf("catch-up-schedule-type")).toBeLessThan(
      testIds.indexOf("catch-up-period-select"),
    );
  });

  it("shows executor label as Исполнитель", () => {
    expect(screen.getByText(`${catchUpUiLabel("executor_role_id")} (опционально)`)).toBeTruthy();
    expect(catchUpUiLabel("executor_role_id")).toBe("Исполнитель");
  });

  it("changes period options when periodicity changes", () => {
    const periodSelect = screen.getByTestId("catch-up-period-select") as HTMLSelectElement;
    const weeklyFirst = periodSelect.options[0]?.textContent ?? "";

    fireEvent.change(screen.getByTestId("catch-up-schedule-type"), { target: { value: "monthly" } });

    const monthlyFirst = (screen.getByTestId("catch-up-period-select") as HTMLSelectElement).options[0]
      ?.textContent;
    expect(monthlyFirst).not.toBe(weeklyFirst);
    expect(monthlyFirst).toMatch(/\d{4}/);
  });

  it("weekly period options display DD.MM–DD.MM range", () => {
    const periodSelect = screen.getByTestId("catch-up-period-select") as HTMLSelectElement;
    expect(periodSelect.options[0]?.textContent).toMatch(/\d{2}\.\d{2}–\d{2}\.\d{2}/);
  });
});
