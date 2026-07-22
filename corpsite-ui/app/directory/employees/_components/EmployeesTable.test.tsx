// FILE: corpsite-ui/app/directory/employees/_components/EmployeesTable.test.tsx
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EmployeesTable from "./EmployeesTable";
import {
  HR_DOSSIER_MISSING_EMPLOYEE_ID_TOOLTIP,
  OPEN_HR_DOSSIER_CTA,
  OPEN_PERSONAL_CARD_CTA,
} from "@/lib/personnelCardTerminology";

describe("EmployeesTable actions", () => {
  afterEach(() => {
    cleanup();
  });

  const baseProps = {
    items: [{ employee_id: 42, fio: "Иванов Иван", status: "active", employment_rate: 1 }],
    total: 1,
    limit: 50,
    offset: 0,
    loading: false,
    onOpenEmployee: vi.fn(),
    onChangePage: vi.fn(),
  };

  it("staff «Персонал»: single «Открыть» link to canonical PPR card when person_id known", () => {
    const onOpenEmployee = vi.fn();
    render(
      <EmployeesTable
        {...baseProps}
        items={[{ employee_id: 42, person_id: 501, fio: "Иванов Иван", status: "active", employment_rate: 1 }]}
        onOpenEmployee={onOpenEmployee}
        managementView
        directPersonalCardNav
      />,
    );

    const openLink = screen.getByRole("link", { name: OPEN_PERSONAL_CARD_CTA });
    expect(openLink).toHaveAttribute("href", "/directory/personnel/persons/501/card");
    expect(openLink).toHaveTextContent("Открыть");
    expect(screen.queryByRole("button", { name: "Открыть" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: OPEN_HR_DOSSIER_CTA })).not.toBeInTheDocument();
    expect(screen.queryByText("Карточка")).not.toBeInTheDocument();

    fireEvent.click(openLink);
    expect(onOpenEmployee).not.toHaveBeenCalled();
  });

  it("staff «Персонал»: falls back to employee compatibility route without person_id", () => {
    const onOpenEmployee = vi.fn();
    render(
      <EmployeesTable
        {...baseProps}
        onOpenEmployee={onOpenEmployee}
        managementView
        directPersonalCardNav
      />,
    );

    const openLink = screen.getByRole("link", { name: OPEN_PERSONAL_CARD_CTA });
    expect(openLink).toHaveAttribute("href", "/directory/personnel/employees/42/card");
    expect(openLink).toHaveTextContent("Открыть");
    expect(screen.queryByRole("button", { name: "Открыть" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: OPEN_HR_DOSSIER_CTA })).not.toBeInTheDocument();
    expect(screen.queryByText("Карточка")).not.toBeInTheDocument();

    fireEvent.click(openLink);
    expect(onOpenEmployee).not.toHaveBeenCalled();
  });

  it("staff row without employee_id disables «Открыть» with tooltip", () => {
    render(
      <EmployeesTable
        {...baseProps}
        items={[{ fio: "Без ID", status: "active" }]}
        managementView
        directPersonalCardNav
      />,
    );

    const disabled = screen.getByRole("button", { name: HR_DOSSIER_MISSING_EMPLOYEE_ID_TOOLTIP });
    expect(disabled).toBeDisabled();
    expect(screen.queryByRole("link", { name: OPEN_PERSONAL_CARD_CTA })).not.toBeInTheDocument();
  });

  it("editable employees list keeps drawer «Открыть» button", () => {
    const onOpenEmployee = vi.fn();
    render(
      <EmployeesTable
        {...baseProps}
        onOpenEmployee={onOpenEmployee}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Открыть" }));
    expect(onOpenEmployee).toHaveBeenCalledWith("42");
    expect(screen.queryByRole("link", { name: OPEN_PERSONAL_CARD_CTA })).not.toBeInTheDocument();
  });

  it("HR personnel journal keeps single card link as «Открыть»", () => {
    render(
      <EmployeesTable
        {...baseProps}
        showCard2Button
      />,
    );

    expect(screen.getByRole("link", { name: OPEN_HR_DOSSIER_CTA })).toHaveAttribute(
      "href",
      "/directory/personnel/employees/42/card",
    );
    expect(screen.queryByRole("button", { name: "Открыть" })).not.toBeInTheDocument();
    expect(screen.queryByText("Карточка")).not.toBeInTheDocument();
  });
});
