// FILE: corpsite-ui/app/directory/employees/_components/EmployeeDrawer.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import EmployeeDrawer from "./EmployeeDrawer";
import { getEmployee } from "../_lib/api.client";
import { apiAuthMe } from "@/lib/api";
import type { EmployeeDetails } from "../_lib/types";

vi.mock("../_lib/api.client", () => ({
  getEmployee: vi.fn(),
  getEmployees: vi.fn(),
  getPositions: vi.fn(),
  mapApiErrorToMessage: vi.fn((e: unknown) => String(e)),
  transferEmployee: vi.fn(),
  updateEmployee: vi.fn(),
  createUser: vi.fn(),
  updateUserRole: vi.fn(),
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

describe("EmployeeDrawer read-only contract (/directory/staff)", () => {
  beforeEach(() => {
    vi.mocked(getEmployee).mockResolvedValue(activeEmployee);
    vi.mocked(apiAuthMe).mockResolvedValue({ user_id: 10, role_id: 5 });
  });

  it("shows Доступ summary but hides HR/account mutations when readOnly is true", async () => {
    render(
      <EmployeeDrawer
        employeeId="42"
        open
        readOnly
        onClose={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Иванов Иван Иванович")).toBeInTheDocument();
    });

    expect(screen.getByRole("heading", { name: "Доступ" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("□ Учётная запись Corpsite ещё не создана")).toBeInTheDocument();
    });

    expect(screen.getByText("Telegram")).toBeInTheDocument();

    expect(screen.queryByRole("button", { name: "Изменить" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Перевести" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Сохранить" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Создать доступ к Corpsite" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Изменить роль Corpsite" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Закрыть" })).toBeInTheDocument();
  });

  it("allows privileged operator to edit Corpsite role from read-only staff drawer", async () => {
    vi.mocked(getEmployee).mockResolvedValue(employeeWithAccount);
    vi.mocked(apiAuthMe).mockResolvedValue({ user_id: 1, role_id: 2, is_privileged: true });

    render(
      <EmployeeDrawer
        employeeId="42"
        open
        readOnly
        onClose={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("ivanov.ii")).toBeInTheDocument();
    });

    expect(screen.getByText("Руководитель ОВЭиПД")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Изменить роль Corpsite" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Создать доступ к Corpsite" })).not.toBeInTheDocument();
  });
});
