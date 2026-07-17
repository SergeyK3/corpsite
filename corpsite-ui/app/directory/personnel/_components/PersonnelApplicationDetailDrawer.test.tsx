import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelApplicationDetailDrawer from "./PersonnelApplicationDetailDrawer";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...rest
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const getPersonnelApplicationMock = vi.fn();

vi.mock("../_lib/personnelApplicationsApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelApplicationsApi.client")>(
    "../_lib/personnelApplicationsApi.client",
  );
  return {
    ...actual,
    getPersonnelApplication: (...args: unknown[]) => getPersonnelApplicationMock(...args),
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelApplicationDetailDrawer", () => {
  it("loads and shows read-only application details", async () => {
    getPersonnelApplicationMock.mockResolvedValue({
      application_id: 10,
      person_id: 5,
      full_name: "Петров Пётр Петрович",
      iin: "900101300123",
      status: "registered",
      application_received_at: "2026-07-01",
      application_source: "paper",
      vacancy_check_status: "confirmed_visually",
      intended_org_unit_name: "Терапия",
      intended_org_group_name: "Группа",
      intended_position_name: "Медсестра",
      intended_employment_rate: 1,
      contact_mobile_phone: "+77001234567",
      contact_email: "petrov@example.com",
      director_resolution_status: "approved",
      director_resolution_at: "2026-07-05T12:00:00Z",
      director_resolution_note: "Одобрено",
      personnel_order_id: 99,
      registered_at: "2026-07-02T10:00:00Z",
      registered_by_user_id: 7,
      registered_by_name: "HR User",
      created_at: "2026-07-02T10:00:00Z",
      updated_at: "2026-07-02T10:00:00Z",
    });

    render(<PersonnelApplicationDetailDrawer applicationId={10} open journalReturnHref="/directory/personnel-applications?application_id=10" onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-application-detail-drawer")).toBeInTheDocument();
    });

    expect(screen.getByText("Петров Пётр Петрович")).toBeInTheDocument();
    expect(screen.getByText("Терапия")).toBeInTheDocument();
    expect(screen.getByText("Медсестра")).toBeInTheDocument();
    expect(screen.getByText("+77001234567")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть личную карточку" })).toHaveAttribute(
      "href",
      "/directory/personnel/persons/5/card?return_to=%2Fdirectory%2Fpersonnel-applications%3Fapplication_id%3D10",
    );
    expect(screen.queryByRole("button", { name: /сохранить/i })).not.toBeInTheDocument();
  });

  it("shows employment section for completed application", async () => {
    getPersonnelApplicationMock.mockResolvedValue({
      application_id: 10,
      person_id: 5,
      full_name: "Петров Пётр Петрович",
      iin: "900101300123",
      status: "completed",
      application_received_at: "2026-07-01",
      application_source: "paper",
      vacancy_check_status: "confirmed_visually",
      intended_org_unit_name: "Терапия",
      intended_position_name: "Медсестра",
      personnel_order_id: 99,
      personnel_order_number: "12-к",
      personnel_order_date: "2026-07-09",
      employee_id: 42,
      employee_full_name: "Петров Пётр Петрович",
      employee_created_at: "2026-07-10T12:00:00Z",
      hire_applied_at: "2026-07-10T12:00:00Z",
      is_read_only: true,
      registered_at: "2026-07-02T10:00:00Z",
      registered_by_user_id: 7,
      registered_by_name: "HR User",
      created_at: "2026-07-02T10:00:00Z",
      updated_at: "2026-07-10T12:00:00Z",
    });

    render(
      <PersonnelApplicationDetailDrawer
        applicationId={10}
        open
        journalReturnHref="/directory/personnel-applications?application_id=10"
        onClose={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("personnel-application-employment-section")).toBeInTheDocument();
    });

    expect(screen.getByTestId("personnel-application-employee-link")).toHaveAttribute(
      "href",
      "/directory/personnel/employees/42/card?return_to=%2Fdirectory%2Fpersonnel-applications%3Fapplication_id%3D10",
    );
    expect(screen.queryByTestId("application-apply-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("intake-issue-link-button")).not.toBeInTheDocument();
  });
});
