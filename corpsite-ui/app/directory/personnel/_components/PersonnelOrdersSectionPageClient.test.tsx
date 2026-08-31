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

vi.mock("./PersonnelOrdersSummaryReport", () => ({
  default: () => <div>Общая сводка по приказам</div>,
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
});
