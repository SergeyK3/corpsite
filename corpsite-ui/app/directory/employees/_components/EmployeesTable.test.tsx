// FILE: corpsite-ui/app/directory/employees/_components/EmployeesTable.test.tsx
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EmployeesTable from "./EmployeesTable";
import {
  HR_DOSSIER_MISSING_EMPLOYEE_ID_TOOLTIP,
  OPEN_HR_DOSSIER_CTA,
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

  it("shows the effective assignment type and an explicit missing value", () => {
    render(<EmployeesTable {...baseProps} managementView items={[
      { employee_id: 42, fio: "Первый", status: "active", type_name: "Врачи" },
      { employee_id: 43, fio: "Второй", status: "active", type_name: null },
    ] as any} />);
    expect(screen.getByRole("columnheader", { name: "Тип" })).toBeInTheDocument();
    expect(screen.getByText("Врачи")).toBeInTheDocument();
    expect(screen.getByText("Не указан")).toBeInTheDocument();
  });

  it("shows status correction next to the staff card action when permitted", () => {
    const onCorrectEmployeeStatus = vi.fn();
    render(
      <EmployeesTable
        {...baseProps}
        managementView
        directPersonalCardNav
        onCorrectEmployeeStatus={onCorrectEmployeeStatus}
      />,
    );
    fireEvent.click(screen.getByTestId("employee-status-correction-open-42"));
    expect(screen.getByTestId("employee-status-correction-open-42")).toHaveClass("bg-blue-600");
    expect(onCorrectEmployeeStatus).toHaveBeenCalledWith(
      expect.objectContaining({ employee_id: 42 }),
    );
  });

  it("staff: preserves the task link and opens the selected Person card with list filters", () => {
    const onOpenEmployee = vi.fn();
    render(
      <EmployeesTable
        {...baseProps}
        items={[{ employee_id: 42, person_id: 501, fio: "Иванов Иван", status: "active", employment_rate: 1 }]}
        onOpenEmployee={onOpenEmployee}
        managementView
        directPersonalCardNav
        returnToHref="/directory/staff?q=Ivanov&org_unit_id=8"
      />,
    );

    const openLink = screen.getByRole("link", { name: "Задачи" });
    expect(openLink).toHaveAttribute("href", "/tasks");
    expect(openLink).toHaveTextContent("Задачи");
    expect(screen.getByRole("link", { name: "Личная карточка" })).toHaveAttribute(
      "href", "/directory/personnel/persons/501/card?return_to=%2Fdirectory%2Fstaff%3Fq%3DIvanov%26org_unit_id%3D8",
    );
    expect(screen.queryByRole("button", { name: "Открыть" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: OPEN_HR_DOSSIER_CTA })).not.toBeInTheDocument();
    expect(screen.queryByText("Карточка")).not.toBeInTheDocument();

    openLink.addEventListener("click", event => event.preventDefault());
    fireEvent.click(openLink);
    expect(onOpenEmployee).not.toHaveBeenCalled();
  });

  it("staff: explains why the Person card is unavailable without person_id", () => {
    const onOpenEmployee = vi.fn();
    render(
      <EmployeesTable
        {...baseProps}
        onOpenEmployee={onOpenEmployee}
        managementView
        directPersonalCardNav
      />,
    );

    const openLink = screen.getByRole("link", { name: "Задачи" });
    expect(openLink).toHaveAttribute("href", "/tasks");
    expect(openLink).toHaveTextContent("Задачи");
    expect(screen.getByRole("button", { name: "Личная карточка недоступна: нет связи с Person" })).toBeDisabled();
    expect(screen.getByText("Нет связи с личной карточкой")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Открыть" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: OPEN_HR_DOSSIER_CTA })).not.toBeInTheDocument();
    expect(screen.queryByText("Карточка")).not.toBeInTheDocument();

    openLink.addEventListener("click", event => event.preventDefault());
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
    expect(screen.queryByRole("link", { name: "Задачи" })).not.toBeInTheDocument();
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
    expect(screen.queryByRole("link", { name: "Задачи" })).not.toBeInTheDocument();
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

  it("shows sysadmin delete button when enabled", () => {
    const onDeleteEmployee = vi.fn();
    render(
      <EmployeesTable
        {...baseProps}
        managementView
        directPersonalCardNav
        showAdminDelete
        onDeleteEmployee={onDeleteEmployee}
      />,
    );

    const deleteButton = screen.getByRole("button", { name: "Удалить Иванов Иван" });
    expect(deleteButton).toBeInTheDocument();
    fireEvent.click(deleteButton);
    expect(onDeleteEmployee).toHaveBeenCalledWith(
      expect.objectContaining({ employee_id: 42, fio: "Иванов Иван" }),
    );
  });

  it("shows unverified termination warning and completion action", () => {
    const onOpenEmployee = vi.fn();
    render(
      <EmployeesTable
        {...baseProps}
        items={[{
          employee_id: 42,
          person_id: 501,
          fio: "Архивный сотрудник",
          status: "inactive",
          employment_rate: 1,
          date_to: null,
          termination: {
            record_id: 7,
            verification_status: "UNVERIFIED",
            termination_date: null,
            order_number: null,
            order_date: null,
          },
        }]}
        onOpenEmployee={onOpenEmployee}
        managementView
        directPersonalCardNav
      />,
    );

    expect(screen.getByText("Сведения не верифицированы")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Заполнить сведения об увольнении" }));
    expect(onOpenEmployee).toHaveBeenCalledWith("42");
  });

  it("shows the unverified termination warning without completion action in read-only view", () => {
    render(
      <EmployeesTable
        {...baseProps}
        items={[{
          employee_id: 42,
          person_id: 501,
          fio: "Архивный сотрудник",
          status: "inactive",
          employment_rate: 1,
          termination: {
            record_id: 7,
            verification_status: "UNVERIFIED",
            termination_date: null,
            order_number: null,
            order_date: null,
          },
        }]}
      />,
    );

    expect(screen.getByText("Сведения не верифицированы")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Заполнить сведения об увольнении" })).not.toBeInTheDocument();
  });

  it("hides delete button for non-sysadmin staff view", () => {
    render(
      <EmployeesTable
        {...baseProps}
        managementView
        directPersonalCardNav
      />,
    );

    expect(screen.queryByRole("button", { name: /Удалить/ })).not.toBeInTheDocument();
  });
});
