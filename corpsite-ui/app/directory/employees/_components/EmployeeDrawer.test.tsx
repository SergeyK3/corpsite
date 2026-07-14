// FILE: corpsite-ui/app/directory/employees/_components/EmployeeDrawer.test.tsx
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EmployeeDrawer from "./EmployeeDrawer";
import { OPEN_HR_DOSSIER_CTA, WORKING_EMPLOYEE_CARD_TITLE } from "@/lib/personnelCardTerminology";
import { getEmployee } from "../_lib/api.client";
import { apiAuthMe } from "@/lib/api";
import type { EmployeeDetails } from "../_lib/types";

vi.mock("../_lib/api.client", () => ({
  getEmployee: vi.fn(),
  mapApiErrorToMessage: vi.fn((e: unknown) => String(e)),
}));

vi.mock("@/lib/api", () => ({
  apiAuthMe: vi.fn(),
}));

const activeEmployee: EmployeeDetails = {
  id: 42,
  employee_id: 42,
  fio: "Иванов Иван Иванович",
  status: "active",
  employment_rate: 1,
  date_from: "2020-01-01",
  date_to: null,
  position: { id: 3, name: "Заведующий отделением" },
  org_unit: { unit_id: 7, name: "Терапия" },
} as EmployeeDetails;

const employeeWithAccount: EmployeeDetails = {
  ...activeEmployee,
  user: {
    login: "ivanov.ii",
    role_name: "Руководитель ОВЭиПД",
    is_active: true,
  },
} as EmployeeDetails;

describe("EmployeeDrawer preview contract", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.mocked(getEmployee).mockResolvedValue(activeEmployee);
    vi.mocked(apiAuthMe).mockResolvedValue({ user_id: 10, role_id: 5 });
  });

  it("shows read-only summary without mutation actions", async () => {
    render(<EmployeeDrawer employeeId="42" open onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: WORKING_EMPLOYEE_CARD_TITLE })).toBeInTheDocument();
      expect(screen.getByText("Иванов Иван Иванович")).toBeInTheDocument();
    });

    expect(screen.getByRole("heading", { name: "Основные сведения" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Текущее назначение" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Доступ" })).toBeInTheDocument();

    expect(screen.queryByRole("button", { name: "Изменить" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Перевести" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Сохранить" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Создать доступ к Corpsite" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Изменить роль Corpsite" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Закрыть" })).toBeInTheDocument();
  });

  it("shows HR card link for personnel admin", async () => {
    vi.mocked(apiAuthMe).mockResolvedValue({ user_id: 4, role_id: 3, has_personnel_admin: true });

    render(<EmployeeDrawer employeeId="42" open onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("link", { name: OPEN_HR_DOSSIER_CTA })).toHaveAttribute(
        "href",
        "/directory/personnel/employees/42/card",
      );
    });
  });

  it("hides HR card link for management browse users", async () => {
    vi.mocked(apiAuthMe).mockResolvedValue({
      user_id: 10,
      role_id: 5,
      show_org_sidebar: true,
      has_personnel_visibility: true,
    });

    render(<EmployeeDrawer employeeId="42" open onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: WORKING_EMPLOYEE_CARD_TITLE })).toBeInTheDocument();
      expect(screen.getByText("Иванов Иван Иванович")).toBeInTheDocument();
    });

    expect(screen.queryByRole("link", { name: OPEN_HR_DOSSIER_CTA })).not.toBeInTheDocument();
  });

  it("shows compact account summary when user is linked", async () => {
    vi.mocked(getEmployee).mockResolvedValue(employeeWithAccount);

    render(<EmployeeDrawer employeeId="42" open onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText(/логин ivanov\.ii/)).toBeInTheDocument();
    });
  });
});
