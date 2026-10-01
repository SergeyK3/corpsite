import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EmployeeAccessOverviewSection from "./EmployeeAccessOverviewSection";

const getEmployeeAccessStateMock = vi.fn();
const getEmployeeTerminationPreviewMock = vi.fn();
const resetEmployeePasswordMock = vi.fn();

vi.mock("../_lib/employeeAccessApi.client", () => ({
  getEmployeeAccessState: (...args: unknown[]) => getEmployeeAccessStateMock(...args),
  getEmployeeTerminationPreview: (...args: unknown[]) => getEmployeeTerminationPreviewMock(...args),
  resetEmployeePassword: (...args: unknown[]) => resetEmployeePasswordMock(...args),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("EmployeeAccessOverviewSection", () => {
  it("renders only safe access facts and aggregate preview data", async () => {
    getEmployeeAccessStateMock.mockResolvedValue({
      employee_id: 42, person_id: 7, user_id: 19, has_linked_user: true,
      employee_is_active: true, is_active: true, must_change_password: false,
      lock_active: true, lock_reason: "brute_force", automatic_lock_active: true,
      locked_until: "2026-09-22T12:00:00+00:00", token_version: 4,
      has_active_assignment: true, generated_at: "2026-09-22T10:00:00+00:00",
    });
    getEmployeeTerminationPreviewMock.mockResolvedValue({
      employee_id: 42, person_id: 7, user_id: 19, linkage_state: "RESOLVED",
      has_linked_user: true, employee_is_active: true, has_active_assignment: true,
      has_applied_approved_termination_event: false,
      counts: {
        unfinished_personal_tasks: 2, active_personal_approvals: 1,
        active_incoming_document_assignments: 3, pending_notifications_deliveries: 4,
        active_direct_grants_by_target_type: { USER: 1, EMPLOYEE: 0, PERSON: null, ASSIGNMENT: 2 },
        dependency_status: {},
      },
      warnings: ["ACTIVE_DIRECT_GRANTS_PRESENT"], generated_at: "2026-09-22T10:00:00+00:00",
    });

    render(<EmployeeAccessOverviewSection employeeId="42" />);

    await waitFor(() => expect(screen.getByTestId("employee-access-overview")).toBeInTheDocument());
    expect(getEmployeeAccessStateMock).toHaveBeenCalledWith("42", { signal: expect.any(AbortSignal) });
    expect(getEmployeeTerminationPreviewMock).toHaveBeenCalledWith("42", { signal: expect.any(AbortSignal) });
    expect(screen.getByText("brute_force")).toBeInTheDocument();
    expect(screen.getByText("token_version")).toBeInTheDocument();
    expect(screen.getByText("ACTIVE_DIRECT_GRANTS_PRESENT")).toBeInTheDocument();
    expect(screen.queryByText(/password_hash|telegram_id|google_login/i)).not.toBeInTheDocument();
  });

  it("keeps the preview visible when the state endpoint reports unresolved linkage", async () => {
    getEmployeeAccessStateMock.mockRejectedValue(new Error("409"));
    getEmployeeTerminationPreviewMock.mockResolvedValue({
      employee_id: 42, person_id: 7, user_id: null, linkage_state: "USER_MISSING",
      has_linked_user: false, employee_is_active: true, has_active_assignment: true,
      has_applied_approved_termination_event: null,
      counts: {
        unfinished_personal_tasks: null, active_personal_approvals: null,
        active_incoming_document_assignments: null, pending_notifications_deliveries: null,
        active_direct_grants_by_target_type: { USER: null, EMPLOYEE: null, PERSON: null, ASSIGNMENT: null },
        dependency_status: {},
      },
      warnings: ["LINKAGE_USER_MISSING"], generated_at: "2026-09-22T10:00:00+00:00",
    });

    render(<EmployeeAccessOverviewSection employeeId="42" />);

    expect(await screen.findByTestId("employee-access-overview")).toBeInTheDocument();
    expect(screen.getByText("USER_MISSING")).toBeInTheDocument();
    expect(screen.getByText("LINKAGE_USER_MISSING")).toBeInTheDocument();
    expect(screen.queryByTestId("issue-temporary-password")).not.toBeInTheDocument();
  });

  it("confirms reset and shows the temporary password only after the response", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
    getEmployeeAccessStateMock.mockResolvedValue({
      employee_id: 42, person_id: 7, user_id: 19, has_linked_user: true,
      employee_is_active: true, is_active: true, must_change_password: false,
      lock_active: false, lock_reason: null, automatic_lock_active: false,
      locked_until: null, token_version: 4, has_active_assignment: true, generated_at: "now",
    });
    getEmployeeTerminationPreviewMock.mockResolvedValue({
      employee_id: 42, person_id: 7, user_id: 19, linkage_state: "RESOLVED", has_linked_user: true,
      employee_is_active: true, has_active_assignment: true, has_applied_approved_termination_event: false,
      counts: { unfinished_personal_tasks: 0, active_personal_approvals: 0, active_incoming_document_assignments: 0, pending_notifications_deliveries: 0, active_direct_grants_by_target_type: {}, dependency_status: {} },
      warnings: [], generated_at: "now",
    });
    resetEmployeePasswordMock.mockResolvedValue({
      employee_id: 42, user_id: 19, temporary_password: "temporary-only-for-test", must_change_password: true,
      temp_password_expires_at: "2026-09-23T10:00:00+00:00", token_version: 5, brute_force_lock_cleared: false,
    });

    render(<EmployeeAccessOverviewSection employeeId="42" />);
    const button = await screen.findByTestId("issue-temporary-password");
    expect(screen.queryByTestId("temporary-password-result")).not.toBeInTheDocument();
    fireEvent.click(button);
    await waitFor(() => expect(resetEmployeePasswordMock).toHaveBeenCalledWith("42"));
    expect(screen.getByTestId("temporary-password-value")).toHaveTextContent("temporary-only-for-test");
    expect(screen.getByText(/Передайте пароль сотруднику безопасным каналом/)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("copy-temporary-password"));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith("temporary-only-for-test"));
  });
});
