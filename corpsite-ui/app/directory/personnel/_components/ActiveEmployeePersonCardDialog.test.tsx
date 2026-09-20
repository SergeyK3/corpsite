import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ActiveEmployeePersonCardDialog from "./ActiveEmployeePersonCardDialog";

const applyMock = vi.fn();
vi.mock("../_lib/personnelMigrationApi.client", () => ({
  applyActiveEmployeePersonCard: (...args: unknown[]) => applyMock(...args),
}));

const ready = { employee_id: 228, employee_full_name: "Employee", operational_status: "active", iin: { present: true, last4: "0451" }, person_candidates: [], ready: true, blockers: [], expected_precondition: "a".repeat(64) };

describe("ActiveEmployeePersonCardDialog", () => {
  it("requires explicit HR confirmation and applies the active-employee endpoint", async () => {
    applyMock.mockResolvedValue({ request_id: "r", employee_id: 228, person_id: 44, decision: "CREATE", employee_full_name: "Employee" });
    const onCreated = vi.fn();
    render(<ActiveEmployeePersonCardDialog employeeId={228} employeeName="Employee" preflight={ready} onClose={vi.fn()} onCreated={onCreated} />);
    expect(screen.getByRole("button", { name: "Подтвердить создание" })).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Подтверждаю создание личной карточки"));
    fireEvent.click(screen.getByRole("button", { name: "Подтвердить создание" }));
    await waitFor(() => expect(applyMock).toHaveBeenCalledWith(expect.objectContaining({ employee_id: 228, expected_precondition: ready.expected_precondition })));
    expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ person_id: 44 }));
  });

  it("shows preflight blockers and cannot apply", () => {
    render(<ActiveEmployeePersonCardDialog employeeId={228} employeeName="Employee" preflight={{ ...ready, ready: false, expected_precondition: null, blockers: [{ code: "PERSON_ALREADY_EXISTS", detail: "Existing Person" }] }} onClose={vi.fn()} onCreated={vi.fn()} />);
    expect(screen.getByText("PERSON_ALREADY_EXISTS")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Подтвердить создание" })).toBeDisabled();
  });
});
