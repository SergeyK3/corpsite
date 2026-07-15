// FILE: corpsite-ui/app/directory/employees/_components/EmployeesTable.test.tsx
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EmployeesTable from "./EmployeesTable";
import {
  HR_DOSSIER_JOURNAL_ACTION,
  HR_DOSSIER_JOURNAL_ACTION_LEGACY,
  HR_DOSSIER_MISSING_EMPLOYEE_ID_TOOLTIP,
  OPEN_HR_DOSSIER_CTA,
  OPEN_PERSONAL_CARD_CTA,
} from "@/lib/personnelCardTerminology";

describe("EmployeesTable journal actions", () => {
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

  it("shows working-card «Открыть» and HR dossier «Карточка» in legacy management read-only view", () => {
    render(
      <EmployeesTable
        {...baseProps}
        managementView
        showHrDossierLink
      />,
    );

    expect(screen.getByRole("button", { name: "Открыть" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: OPEN_HR_DOSSIER_CTA })).toHaveAttribute(
      "href",
      "/directory/personnel/employees/42/card",
    );
    expect(screen.getByRole("link", { name: OPEN_HR_DOSSIER_CTA })).toHaveTextContent(
      HR_DOSSIER_JOURNAL_ACTION_LEGACY,
    );
  });

  it("navigates directly to personal card when openPersonalCardDirectly is enabled", () => {
    render(
      <EmployeesTable
        {...baseProps}
        managementView
        openPersonalCardDirectly
      />,
    );

    expect(screen.getByRole("link", { name: OPEN_PERSONAL_CARD_CTA })).toHaveAttribute(
      "href",
      "/directory/personnel/employees/42/card",
    );
    expect(screen.getByRole("link", { name: OPEN_PERSONAL_CARD_CTA })).toHaveTextContent(
      HR_DOSSIER_JOURNAL_ACTION,
    );
    expect(screen.queryByRole("button", { name: "Открыть" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: OPEN_HR_DOSSIER_CTA })).not.toBeInTheDocument();
  });

  it("disables HR dossier «Карточка» with tooltip when employee_id is missing", () => {
    render(
      <EmployeesTable
        {...baseProps}
        items={[{ fio: "Без ID", status: "active" }]}
        managementView
        showHrDossierLink
      />,
    );

    const cardButton = screen.getByRole("button", { name: HR_DOSSIER_MISSING_EMPLOYEE_ID_TOOLTIP });
    expect(cardButton).toBeDisabled();
    expect(cardButton).toHaveTextContent(HR_DOSSIER_JOURNAL_ACTION);
    expect(cardButton.closest("span")).toHaveAttribute("title", HR_DOSSIER_MISSING_EMPLOYEE_ID_TOOLTIP);
    expect(screen.queryByRole("button", { name: "Открыть" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: OPEN_HR_DOSSIER_CTA })).not.toBeInTheDocument();
  });

  it("keeps HR personnel route card link as single «Открыть» action", () => {
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
    expect(screen.queryByRole("link", { name: HR_DOSSIER_JOURNAL_ACTION_LEGACY })).not.toBeInTheDocument();
  });
});
