import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import StaffPageClient from "./StaffPageClient";

const navigation = vi.hoisted(() => ({
  params: "",
  replace: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: navigation.replace }),
  useSearchParams: () => new URLSearchParams(navigation.params),
}));

vi.mock("../../employees/_components/EmployeesPageClient", () => ({
  default: () => <div>Рабочий список персонала</div>,
}));

vi.mock("../../personnel/_components/PersonnelRosterReport", () => ({
  default: () => <div>Отчёт «Личный состав»</div>,
}));

afterEach(() => {
  cleanup();
  navigation.params = "";
  navigation.replace.mockReset();
});

describe("StaffPageClient", () => {
  it("opens personnel by default and switches directly to its report", () => {
    navigation.params = "q=Иванов";
    render(<StaffPageClient />);

    expect(screen.getByRole("button", { name: "Персонал" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Рабочий список персонала")).toBeInTheDocument();
    expect(screen.queryByText("Отчёт «Личный состав»")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Отчёты" }));

    expect(screen.getByRole("button", { name: "Отчёты" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Отчёт «Личный состав»")).toBeInTheDocument();
    expect(screen.queryByText("Рабочий список персонала")).not.toBeInTheDocument();
    expect(navigation.replace).toHaveBeenCalledWith("/directory/staff?q=%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2&view=reports");
  });

  it("opens the report directly from view=reports", () => {
    navigation.params = "view=reports";
    render(<StaffPageClient />);

    expect(screen.getByRole("button", { name: "Отчёты" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Отчёт «Личный состав»")).toBeInTheDocument();
  });
});
