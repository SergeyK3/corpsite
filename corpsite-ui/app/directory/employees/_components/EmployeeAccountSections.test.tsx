import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EmployeeAccountSections from "./EmployeeAccountSections";
import { createUser, getEmployee, updateUserRole } from "../_lib/api.client";

vi.mock("../_lib/api.client", () => ({
  createUser: vi.fn(),
  getEmployee: vi.fn(),
  updateUserRole: vi.fn(),
}));

vi.mock("@/lib/userCreateOrgScope", () => ({
  employeeOrgUnitId: vi.fn(() => null),
  resolveEmployeeOrgScopePrefill: vi.fn().mockResolvedValue({ org_group_id: null, org_unit_id: null }),
}));

vi.mock("./EmployeeEventsTimeline", () => ({
  default: () => <div data-testid="employee-events-timeline" />,
}));

vi.mock("./UserCreateDrawer", () => ({
  default: ({ open }: { open: boolean }) =>
    open ? <div data-testid="user-create-drawer">user-create-drawer</div> : null,
}));

vi.mock("./UserRoleEditDrawer", () => ({
  default: ({ open, onSubmit }: { open: boolean; onSubmit: (roleId: number) => void }) =>
    open ? (
      <div data-testid="user-role-edit-drawer">
        <button type="button" onClick={() => onSubmit(8)}>
          save-role
        </button>
      </div>
    ) : null,
}));

describe("EmployeeAccountSections provisioning UX", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows pending account message and create button when user is missing", async () => {
    vi.mocked(getEmployee).mockResolvedValue({
      employee_id: 100,
      fio: "Козгамбаева Ляззат",
      user: null,
    } as Awaited<ReturnType<typeof getEmployee>>);

    render(<EmployeeAccountSections employeeId="100" showEvents={false} showTelegram={false} />);

    await waitFor(() => {
      expect(screen.getByText("□ Учётная запись Corpsite ещё не создана")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Создать доступ к Corpsite" })).toBeInTheDocument();
  });

  it("shows existing account confirmation without create button", async () => {
    vi.mocked(getEmployee).mockResolvedValue({
      employee_id: 100,
      fio: "Козгамбаева Ляззат",
      user: {
        login: "kozgambayeva@corp.local",
        role_name: "DEP role",
        is_active: true,
      },
    } as Awaited<ReturnType<typeof getEmployee>>);

    render(<EmployeeAccountSections employeeId="100" showEvents={false} showTelegram={false} />);

    await waitFor(() => {
      expect(screen.getByText("✓ Учётная запись Corpsite существует")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Создать доступ к Corpsite" })).not.toBeInTheDocument();
    expect(screen.getByText("kozgambayeva@corp.local")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Изменить роль Corpsite" })).toBeInTheDocument();
  });

  it("opens role edit drawer and saves updated role", async () => {
    vi.mocked(getEmployee)
      .mockResolvedValueOnce({
        employee_id: 100,
        fio: "Макибаева",
        user: {
          user_id: 361,
          login: "makibaeva.as",
          role_id: 5,
          role_name: "Руководитель ОВЭиПД",
          is_active: true,
        },
      } as Awaited<ReturnType<typeof getEmployee>>)
      .mockResolvedValueOnce({
        employee_id: 100,
        fio: "Макибаева",
        user: {
          user_id: 361,
          login: "makibaeva.as",
          role_id: 8,
          role_name: "Руководитель отдела кадров",
          is_active: true,
        },
      } as Awaited<ReturnType<typeof getEmployee>>);

    vi.mocked(updateUserRole).mockResolvedValue({
      user_id: 361,
      login: "makibaeva.as",
      role_id: 8,
      role_name: "Руководитель отдела кадров",
    } as Awaited<ReturnType<typeof updateUserRole>>);

    render(<EmployeeAccountSections employeeId="100" showEvents={false} showTelegram={false} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Изменить роль Corpsite" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Изменить роль Corpsite" }));

    await waitFor(() => {
      expect(screen.getByTestId("user-role-edit-drawer")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "save-role" }));

    await waitFor(() => {
      expect(updateUserRole).toHaveBeenCalledWith(361, 8);
    });
  });

  it("auto-opens user create drawer when initialUserCreateOpen is true", async () => {
    vi.mocked(getEmployee).mockResolvedValue({
      employee_id: 100,
      fio: "Козгамбаева Ляззат",
      user: null,
    } as Awaited<ReturnType<typeof getEmployee>>);

    render(
      <EmployeeAccountSections
        employeeId="100"
        showEvents={false}
        showTelegram={false}
        initialUserCreateOpen
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("user-create-drawer")).toBeInTheDocument();
    });
  });

  it("opens user create drawer from CTA button", async () => {
    vi.mocked(getEmployee).mockResolvedValue({
      employee_id: 100,
      fio: "Козгамбаева Ляззат",
      user: null,
    } as Awaited<ReturnType<typeof getEmployee>>);

    render(<EmployeeAccountSections employeeId="100" showEvents={false} showTelegram={false} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Создать доступ к Corpsite" })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "Создать доступ к Corpsite" }));

    await waitFor(() => {
      expect(screen.getByTestId("user-create-drawer")).toBeInTheDocument();
    });
    expect(createUser).not.toHaveBeenCalled();
  });
});
