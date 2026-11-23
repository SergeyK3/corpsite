import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelOrdersSectionPageClient from "./PersonnelOrdersSectionPageClient";

const navigation = vi.hoisted(() => ({
  params: "",
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: navigation.replace }),
  useSearchParams: () => new URLSearchParams(navigation.params),
}));

vi.mock("./PersonnelOrdersPageClient", () => ({
  default: () => <div>Рабочее место кадровых приказов</div>,
}));

vi.mock("./PersonnelEmployeeActionsReport", () => ({
  default: () => <div>Кадровые действия по сотрудникам</div>,
}));

vi.mock("./PersonnelOrdersDashboards", () => ({
  default: () => <div data-testid="orders-dashboards">Количество кадровых приказов по месяцам</div>,
}));

vi.mock("./PersonnelOrdersSummaryReport", () => ({
  default: ({ mode }: { mode: string }) => <><div>Общая сводка по приказам</div><span data-testid="orders-summary-mode">{mode}</span></>,
}));

afterEach(() => {
  cleanup();
  navigation.params = "";
  navigation.replace.mockReset();
});

describe("PersonnelOrdersSectionPageClient", () => {
  it("opens кадровые приказы by default and switches to the single report", () => {
    navigation.params = "status=SIGNED";
    render(<PersonnelOrdersSectionPageClient />);

    expect(screen.getByRole("button", { name: "Кадровые приказы" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Рабочее место кадровых приказов")).toBeInTheDocument();
    expect(screen.queryByText("Общая сводка по приказам")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Отчёты" }));

    expect(screen.getByRole("button", { name: "Отчёты" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Общая сводка по приказам")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "По категориям" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "По статусам" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "По типу персонала" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "По сотрудникам" })).toBeInTheDocument();
    expect(screen.getByTestId("orders-summary-mode")).toHaveTextContent("categories");
    expect(screen.queryByText("Кадровые действия по сотрудникам")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "По статусам" }));
    expect(screen.getByTestId("orders-summary-mode")).toHaveTextContent("statuses");
    fireEvent.click(screen.getByRole("button", { name: "По сотрудникам" }));
    expect(screen.getByText("Кадровые действия по сотрудникам")).toBeInTheDocument();
    expect(screen.queryByText("Общая сводка по приказам")).not.toBeInTheDocument();
    expect(screen.queryByText("Рабочее место кадровых приказов")).not.toBeInTheDocument();
    expect(navigation.replace).toHaveBeenCalledWith(
      "/directory/personnel/orders?status=SIGNED&view=reports",
    );
  });

  it("opens the report directly from view=reports", () => {
    navigation.params = "view=reports";
    render(<PersonnelOrdersSectionPageClient />);

    expect(screen.getByRole("button", { name: "Отчёты" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Общая сводка по приказам")).toBeInTheDocument();
  });

  it("opens dashboards after reports while keeping the orders journal as default", () => {
    render(<PersonnelOrdersSectionPageClient />);
    expect(screen.getAllByRole("button").map((button) => button.textContent)).toEqual([
      "Кадровые приказы", "Отчёты", "Дашборды",
    ]);
    expect(screen.getByText("Рабочее место кадровых приказов")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Дашборды" }));
    expect(navigation.replace).toHaveBeenCalledWith("/directory/personnel/orders?view=dashboards");
    expect(screen.getByTestId("orders-dashboards")).toBeInTheDocument();
    expect(screen.queryByText("Общая сводка по приказам")).not.toBeInTheDocument();
  });
});
