import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelApplicationEmploymentSection from "./PersonnelApplicationEmploymentSection";

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

afterEach(() => {
  cleanup();
});

describe("PersonnelApplicationEmploymentSection", () => {
  it("shows employee and order links for completed application", () => {
    render(
      <PersonnelApplicationEmploymentSection
        journalReturnHref="/directory/personnel/applicants?application_id=10"
        detail={{
          application_id: 10,
          person_id: 5,
          status: "completed",
          application_received_at: "2026-07-01",
          application_source: "paper",
          vacancy_check_status: "confirmed_visually",
          registered_at: "2026-07-02T10:00:00Z",
          registered_by_user_id: 7,
          created_at: "2026-07-02T10:00:00Z",
          updated_at: "2026-07-10T12:00:00Z",
          employee_id: 42,
          employee_full_name: "Петров Пётр Петрович",
          employee_created_at: "2026-07-10T12:00:00Z",
          personnel_order_id: 99,
          personnel_order_number: "12-к",
          personnel_order_date: "2026-07-09",
          hire_applied_at: "2026-07-10T12:00:00Z",
        }}
      />,
    );

    expect(screen.getByTestId("personnel-application-employment-section")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-application-employee-link")).toHaveAttribute(
      "href",
      "/directory/personnel/persons/5/card?return_to=%2Fdirectory%2Fpersonnel%2Fapplicants%3Fapplication_id%3D10",
    );
    expect(screen.getByTestId("personnel-application-hire-order-link")).toHaveAttribute(
      "href",
      "/directory/personnel/orders?order_id=99",
    );
    expect(screen.getByText("Петров Пётр Петрович")).toBeInTheDocument();
  });

  it("renders nothing when application is not completed", () => {
    const { container } = render(
      <PersonnelApplicationEmploymentSection
        journalReturnHref="/directory/personnel/applicants"
        detail={{
          application_id: 10,
          person_id: 5,
          status: "approved",
          application_received_at: "2026-07-01",
          application_source: "paper",
          vacancy_check_status: "confirmed_visually",
          registered_at: "2026-07-02T10:00:00Z",
          registered_by_user_id: 7,
          created_at: "2026-07-02T10:00:00Z",
          updated_at: "2026-07-02T10:00:00Z",
        }}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
