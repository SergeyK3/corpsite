import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EmployeeAccountSections from "./EmployeeAccountSections";
import { getEmployee, getRoles } from "../_lib/api.client";

vi.mock("../_lib/api.client", () => ({
  createUser: vi.fn(),
  getEmployee: vi.fn(),
  getRoles: vi.fn(),
}));

vi.mock("./EmployeeEventsTimeline", () => ({
  default: () => <div data-testid="employee-events-timeline" />,
}));

describe("EmployeeAccountSections login suggestion", () => {
  beforeEach(() => {
    vi.mocked(getRoles).mockResolvedValue({
      items: [{ role_id: 5, role_name: "QM role" }],
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("prefills kozgambaeva.lt when opening user create drawer", async () => {
    vi.mocked(getEmployee).mockResolvedValue({
      employee_id: 100,
      fio: "Козгамбаева Ляззат Таласпаевна",
      user: null,
      org_unit: { unit_id: 44, name: "Ambulatory" },
    } as Awaited<ReturnType<typeof getEmployee>>);

    render(<EmployeeAccountSections employeeId="100" showEvents={false} showTelegram={false} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Создать доступ к Corpsite" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Создать доступ к Corpsite" }));

    await waitFor(() => {
      expect(screen.getByLabelText(/Логин/i)).toHaveValue("kozgambaeva.lt");
    });
    expect(screen.getByLabelText(/Логин/i)).not.toHaveValue("talaspaevnak");
  });

  it("prefills kozgambaeva.lt on auto-open after enrollment", async () => {
    vi.mocked(getEmployee).mockResolvedValue({
      employee_id: 100,
      fio: "Козгамбаева Ляззат Таласпаевна",
      user: null,
      org_unit: { unit_id: 44, name: "Ambulatory" },
    } as Awaited<ReturnType<typeof getEmployee>>);

    render(
      <EmployeeAccountSections
        employeeId="100"
        showEvents={false}
        showTelegram={false}
        initialUserCreateOpen
      />,
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Логин/i)).toHaveValue("kozgambaeva.lt");
    });
  });
});
