import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelApplicationDetailDrawer from "./PersonnelApplicationDetailDrawer";
import * as workflow from "../_lib/personnelApplicantWorkflow";

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
const getApplicationTimelineMock = vi.fn();
const getLifecycleAuditMock = vi.fn();
const getIntakeReviewStateMock = vi.fn();

vi.mock("../_lib/personnelApplicationsApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelApplicationsApi.client")>(
    "../_lib/personnelApplicationsApi.client",
  );
  return {
    ...actual,
    getPersonnelApplication: (...args: unknown[]) => getPersonnelApplicationMock(...args),
    getApplicationTimeline: (...args: unknown[]) => getApplicationTimelineMock(...args),
    getLifecycleAudit: (...args: unknown[]) => getLifecycleAuditMock(...args),
    getIntakeReviewState: (...args: unknown[]) => getIntakeReviewStateMock(...args),
  };
});

beforeEach(() => {
  getApplicationTimelineMock.mockResolvedValue({ application_id: 10, items: [] });
  getLifecycleAuditMock.mockResolvedValue({ items: [] });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.restoreAllMocks();
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

    render(<PersonnelApplicationDetailDrawer applicationId={10} open journalReturnHref="/directory/personnel/applicants?application_id=10" onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-application-detail-drawer")).toBeInTheDocument();
    });

    expect(screen.getByText("Петров Пётр Петрович")).toBeInTheDocument();
    expect(screen.getByText("Терапия")).toBeInTheDocument();
    expect(screen.getByText("Медсестра")).toBeInTheDocument();
    expect(screen.getByText("+77001234567")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-application-person-card-locked")).toHaveTextContent(
      /личная карточка станет доступна после проверки анкеты и переноса в ppr/i,
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
        journalReturnHref="/directory/personnel/applicants?application_id=10"
        onClose={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("personnel-application-employment-section")).toBeInTheDocument();
    });

    expect(screen.getByTestId("personnel-application-employee-link")).toHaveAttribute(
      "href",
      "/directory/personnel/persons/5/card?return_to=%2Fdirectory%2Fpersonnel%2Fapplicants%3Fapplication_id%3D10",
    );
    expect(screen.queryByTestId("application-apply-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("intake-issue-link-button")).not.toBeInTheDocument();
  });

  it("loads detail after registerPersonnelApplication and issueIntakeLink without ReferenceError and shows intake link", async () => {
    const intakePath = "/intake/abc123";
    vi.spyOn(workflow, "readPersistedIntakeLinkPath").mockReturnValue(intakePath);

    getPersonnelApplicationMock.mockResolvedValue({
      application_id: 10,
      person_id: 5,
      full_name: "Новый Претендент",
      iin: "900101300123",
      status: "registered",
      application_received_at: "2026-07-17",
      application_source: "paper",
      vacancy_check_status: "confirmed_visually",
      intended_org_unit_name: "Терапия",
      intended_org_group_name: "Группа",
      intended_position_name: "Медсестра",
      intended_employment_rate: 1,
      contact_mobile_phone: "+77001234567",
      contact_email: "new@example.com",
      intake_link_status: "issued",
      intake_draft_status: null,
      registered_at: "2026-07-17T10:00:00Z",
      registered_by_user_id: 7,
      registered_by_name: "HR User",
      created_at: "2026-07-17T10:00:00Z",
      updated_at: "2026-07-17T10:00:00Z",
    });

    render(
      <PersonnelApplicationDetailDrawer
        applicationId={10}
        open
        journalReturnHref="/directory/personnel/applicants?application_id=10"
        onClose={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(getPersonnelApplicationMock).toHaveBeenCalledWith(10);
    });

    expect(screen.getByTestId("personnel-application-detail-drawer")).toBeInTheDocument();
    expect(await screen.findByTestId("personnel-application-intake-link-panel")).toBeInTheDocument();
    expect(screen.getByTestId("intake-copy-link-button")).toHaveTextContent("Скопировать ссылку");
    expect(screen.getByText(/\/intake\/abc123/)).toBeInTheDocument();
    expect(screen.queryByText(/getPersonnelApplication is not defined/i)).not.toBeInTheDocument();
    expect(workflow.readPersistedIntakeLinkPath).toHaveBeenCalledWith(10);
  });

  it("shows intake review action before transfer and hides personal card link", async () => {
    getPersonnelApplicationMock.mockResolvedValue({
      application_id: 178,
      person_id: 534,
      full_name: "Тестов Тест",
      iin: "880315350789",
      status: "intake_submitted",
      application_received_at: "2026-07-17",
      application_source: "paper",
      vacancy_check_status: "confirmed_visually",
      intake_draft_status: "submitted",
      intake_link_status: "submitted",
      registered_at: "2026-07-17T10:00:00Z",
      registered_by_user_id: 7,
      registered_by_name: "HR User",
      created_at: "2026-07-17T10:00:00Z",
      updated_at: "2026-07-17T10:00:00Z",
    });
    getIntakeReviewStateMock.mockResolvedValue({
      application_id: 178,
      sections: [],
      can_transfer: false,
      transfer_blocked_reason: "Section personal is not finalized.",
      transfer: null,
    });

    render(
      <PersonnelApplicationDetailDrawer
        applicationId={178}
        open
        journalReturnHref="/directory/personnel/applicants?application_id=178"
        onClose={vi.fn()}
      />,
    );

    const reviewButton = await screen.findByTestId("personnel-application-open-intake-review");
    expect(reviewButton).toHaveTextContent("Открыть анкету для проверки");
    expect(screen.queryByTestId("personnel-application-open-person-card")).not.toBeInTheDocument();
    expect(screen.queryByTestId("personnel-application-person-card-locked")).not.toBeInTheDocument();

    fireEvent.click(reviewButton);
    await waitFor(() => {
      expect(getIntakeReviewStateMock).toHaveBeenCalledWith(178);
      expect(screen.getByTestId("intake-review-drawer")).toBeInTheDocument();
    });
  });

  it("shows personal card link after transfer completed", async () => {
    getPersonnelApplicationMock.mockResolvedValue({
      application_id: 178,
      person_id: 534,
      full_name: "Тестов Тест",
      iin: "880315350789",
      status: "review_completed",
      application_received_at: "2026-07-17",
      application_source: "paper",
      vacancy_check_status: "confirmed_visually",
      intake_draft_status: "submitted",
      intake_link_status: "submitted",
      registered_at: "2026-07-17T10:00:00Z",
      registered_by_user_id: 7,
      registered_by_name: "HR User",
      created_at: "2026-07-17T10:00:00Z",
      updated_at: "2026-07-17T10:00:00Z",
    });

    render(
      <PersonnelApplicationDetailDrawer
        applicationId={178}
        open
        journalReturnHref="/directory/personnel/applicants?application_id=178"
        onClose={vi.fn()}
      />,
    );

    const cardLink = await screen.findByTestId("personnel-application-open-person-card");
    expect(cardLink).toHaveTextContent("Открыть личную карточку");
    expect(cardLink).toHaveAttribute(
      "href",
      "/directory/personnel/persons/534/card?return_to=%2Fdirectory%2Fpersonnel%2Fapplicants%3Fapplication_id%3D178",
    );
    expect(screen.queryByTestId("personnel-application-open-intake-review")).not.toBeInTheDocument();
  });
});
