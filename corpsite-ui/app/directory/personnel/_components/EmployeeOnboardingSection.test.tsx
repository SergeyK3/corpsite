import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EmployeeOnboardingSection from "./EmployeeOnboardingSection";

const getEmployeeOnboardingByEmployeeIdMock = vi.fn();
const completeOnboardingChecklistItemMock = vi.fn();

vi.mock("../_lib/employeeOnboardingApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/employeeOnboardingApi.client")>(
    "../_lib/employeeOnboardingApi.client",
  );
  return {
    ...actual,
    getEmployeeOnboardingByEmployeeId: (...args: unknown[]) =>
      getEmployeeOnboardingByEmployeeIdMock(...args),
    completeOnboardingChecklistItem: (...args: unknown[]) =>
      completeOnboardingChecklistItemMock(...args),
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("EmployeeOnboardingSection", () => {
  it("loads onboarding and shows progress", async () => {
    getEmployeeOnboardingByEmployeeIdMock.mockResolvedValue({
      onboarding_id: 1,
      employee_id: 42,
      application_id: 10,
      status: "active",
      started_at: "2026-07-01T10:00:00Z",
      planned_end_at: "2026-10-01T10:00:00Z",
      completed_at: null,
      responsible_hr_id: 7,
      mentor_employee_id: null,
      notes: null,
      progress_percent: 17,
      is_read_only: false,
      checklist_items: [
        {
          item_id: 100,
          onboarding_id: 1,
          item_code: "lna_introduction",
          title: "Ознакомление с ЛНА",
          sort_order: 0,
          is_custom: false,
          status: "pending",
          completed_at: null,
          completed_by_user_id: null,
          comment: null,
        },
      ],
    });

    render(<EmployeeOnboardingSection employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByTestId("employee-onboarding-section")).toBeInTheDocument();
    });
    expect(screen.getByTestId("employee-onboarding-progress")).toHaveTextContent("17%");
    expect(screen.getByText("Ознакомление с ЛНА")).toBeInTheDocument();
  });

  it("marks checklist item completed", async () => {
    getEmployeeOnboardingByEmployeeIdMock.mockResolvedValue({
      onboarding_id: 1,
      employee_id: 42,
      application_id: null,
      status: "active",
      started_at: "2026-07-01T10:00:00Z",
      planned_end_at: null,
      completed_at: null,
      responsible_hr_id: 7,
      mentor_employee_id: null,
      notes: null,
      progress_percent: 0,
      is_read_only: false,
      checklist_items: [
        {
          item_id: 100,
          onboarding_id: 1,
          item_code: "lna_introduction",
          title: "Ознакомление с ЛНА",
          sort_order: 0,
          is_custom: false,
          status: "pending",
          completed_at: null,
          completed_by_user_id: null,
          comment: null,
        },
      ],
    });
    completeOnboardingChecklistItemMock.mockResolvedValue({
      onboarding_id: 1,
      employee_id: 42,
      application_id: null,
      status: "active",
      started_at: "2026-07-01T10:00:00Z",
      planned_end_at: null,
      completed_at: null,
      responsible_hr_id: 7,
      mentor_employee_id: null,
      notes: null,
      progress_percent: 17,
      is_read_only: false,
      checklist_items: [
        {
          item_id: 100,
          onboarding_id: 1,
          item_code: "lna_introduction",
          title: "Ознакомление с ЛНА",
          sort_order: 0,
          is_custom: false,
          status: "completed",
          completed_at: "2026-07-02T10:00:00Z",
          completed_by_user_id: 7,
          comment: null,
        },
      ],
    });

    render(<EmployeeOnboardingSection employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByTestId("onboarding-complete-item-100")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("onboarding-complete-item-100"));

    await waitFor(() => {
      expect(completeOnboardingChecklistItemMock).toHaveBeenCalledWith(1, 100);
    });
    expect(screen.getByTestId("employee-onboarding-progress")).toHaveTextContent("17%");
  });

  it("hides actions for read-only completed onboarding", async () => {
    getEmployeeOnboardingByEmployeeIdMock.mockResolvedValue({
      onboarding_id: 1,
      employee_id: 42,
      application_id: null,
      status: "completed",
      started_at: "2026-07-01T10:00:00Z",
      planned_end_at: null,
      completed_at: "2026-07-10T10:00:00Z",
      responsible_hr_id: 7,
      mentor_employee_id: null,
      notes: null,
      progress_percent: 100,
      is_read_only: true,
      checklist_items: [
        {
          item_id: 100,
          onboarding_id: 1,
          item_code: "lna_introduction",
          title: "Ознакомление с ЛНА",
          sort_order: 0,
          is_custom: false,
          status: "completed",
          completed_at: "2026-07-02T10:00:00Z",
          completed_by_user_id: 7,
          comment: null,
        },
      ],
    });

    render(<EmployeeOnboardingSection employeeId="42" />);

    await waitFor(() => {
      expect(screen.getByTestId("employee-onboarding-section")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("onboarding-complete-item-100")).not.toBeInTheDocument();
    expect(screen.queryByTestId("onboarding-complete-program")).not.toBeInTheDocument();
  });
});
