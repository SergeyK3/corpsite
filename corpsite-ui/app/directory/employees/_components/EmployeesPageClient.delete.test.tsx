import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EmployeesPageClient from "./EmployeesPageClient";
import { OPEN_PERSONAL_CARD_CTA } from "@/lib/personnelCardTerminology";
import { CurrentUserProvider } from "@/lib/currentUser";
import type { MeInfo } from "@/lib/types";

const pushMock = vi.fn();
const replaceMock = vi.fn();
const confirmMock = vi.fn();
const deleteEmployeeMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
  usePathname: () => "/directory/staff",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/components/OrgScopeFilter", () => ({
  default: () => <div data-testid="org-scope-filter" />,
}));

vi.mock("./EmployeeDrawer", () => ({
  default: () => <div data-testid="employee-drawer">drawer</div>,
}));

vi.mock("./EmployeeCreateDrawer", () => ({
  default: () => null,
}));

vi.mock("../_lib/api.client", () => ({
  getEmployees: vi.fn(async () => ({
    items: [{ employee_id: 42, person_id: 501, fio: "Иванов Иван", status: "active", employment_rate: 1 }],
    total: 1,
  })),
  getPositions: vi.fn(async () => ({ items: [] })),
  getDepartments: vi.fn(async () => ({ items: [] })),
  mapApiErrorToMessage: (e: unknown) => String(e),
  createEmployee: vi.fn(),
  deleteEmployee: (...args: unknown[]) => deleteEmployeeMock(...args),
}));

vi.mock("../../org-units/_lib/api.client", () => ({
  getOrgUnitsTree: vi.fn(async () => ({ items: [] })),
}));

const baseProps = {
  pageTitle: "Персонал",
  readOnly: true,
  managementView: true,
  initialFilters: { status: "all", limit: 50, offset: 0 },
  initialDepartments: [],
  initialPositions: [],
  initialEmployees: {
    items: [{ employee_id: 42, person_id: 501, fio: "Иванов Иван", status: "active", employment_rate: 1 }],
    total: 1,
  },
  initialError: null,
  refreshResetsOrgUnitFilter: true,
};

function renderWithMe(me: MeInfo | null) {
  return render(
    <CurrentUserProvider value={me}>
      <EmployeesPageClient {...baseProps} />
    </CurrentUserProvider>,
  );
}

beforeEach(() => {
  pushMock.mockReset();
  replaceMock.mockReset();
  confirmMock.mockReset();
  deleteEmployeeMock.mockReset();
  vi.stubGlobal("confirm", confirmMock);
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("EmployeesPageClient staff hard-delete", () => {
  it("shows delete button for canonical system admin profile", async () => {
    renderWithMe({ user_id: 1, role_id: 2, is_system_admin: true, can_hard_delete_employee: true });

    expect(await screen.findByRole("button", { name: "Удалить Иванов Иван" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: OPEN_PERSONAL_CARD_CTA })).toBeInTheDocument();
  });

  it("does not show delete button for sysadmin API user without canonical flag", async () => {
    renderWithMe({
      user_id: 34,
      role_id: 68,
      is_system_admin: false,
      has_sysadmin_api: true,
      can_hard_delete_employee: false,
    });

    await screen.findByRole("link", { name: OPEN_PERSONAL_CARD_CTA });
    expect(screen.queryByRole("button", { name: /Удалить/ })).not.toBeInTheDocument();
  });

  it("confirms, deletes employee and removes row without reload", async () => {
    renderWithMe({ user_id: 1, role_id: 2, is_system_admin: true, can_hard_delete_employee: true });
    confirmMock.mockReturnValue(true);
    deleteEmployeeMock.mockResolvedValue({ ok: true, employee_id: 42, person_deleted: true });

    fireEvent.click(await screen.findByRole("button", { name: "Удалить Иванов Иван" }));

    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining("Иванов Иван"),
    );
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining("Сотрудник и все связанные данные будут удалены без возможности восстановления"),
    );
    await waitFor(() => expect(deleteEmployeeMock).toHaveBeenCalledWith("42"));
    await waitFor(() => expect(screen.queryByText("Иванов Иван")).not.toBeInTheDocument());
    expect(screen.getByText(/Всего: 0/)).toBeInTheDocument();
  });

  it("shows API error and keeps row when delete fails", async () => {
    renderWithMe({ user_id: 1, role_id: 2, is_system_admin: true, can_hard_delete_employee: true });
    confirmMock.mockReturnValue(true);
    deleteEmployeeMock.mockRejectedValue(new Error("HTTP 409: conflict"));

    fireEvent.click(await screen.findByRole("button", { name: "Удалить Иванов Иван" }));

    expect(await screen.findByText(/HTTP 409/)).toBeInTheDocument();
    expect(screen.getByText("Иванов Иван")).toBeInTheDocument();
  });
});
