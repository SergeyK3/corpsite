import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EmployeeAccountSections from "./EmployeeAccountSections";
import { getEmployee } from "../_lib/api.client";

vi.mock("../_lib/api.client", () => ({
  createUser: vi.fn(),
  getEmployee: vi.fn(),
}));

vi.mock("@/lib/userCreateOrgScope", () => ({
  employeeOrgUnitId: vi.fn(() => 44),
  resolveEmployeeOrgScopePrefill: vi
    .fn()
    .mockResolvedValue({ org_group_id: 1, org_unit_id: 44 }),
}));

vi.mock("@/components/OrgScopeFilter", () => ({
  default: ({ label, value }: { label: string; value?: number | null }) => (
    <div data-testid="org-group-filter" data-value={value ?? ""}>
      {label}
    </div>
  ),
}));

vi.mock("@/components/OrgUnitScopeFilter", () => ({
  default: ({
    label,
    orgGroupId,
    value,
  }: {
    label: string;
    orgGroupId?: number | null;
    value?: number | null;
  }) => (
    <div
      data-testid="org-unit-filter"
      data-group-id={orgGroupId ?? ""}
      data-value={value ?? ""}
    >
      {label}
    </div>
  ),
}));

vi.mock("@/lib/platformRoleCatalog", () => ({
  listPlatformRoleCatalog: vi.fn().mockResolvedValue([
    { id: 5, label: "QM Head", code: "QM_HEAD" },
  ]),
}));

vi.mock("./EmployeeEventsTimeline", () => ({
  default: () => <div data-testid="employee-events-timeline" />,
}));

describe("EmployeeAccountSections login suggestion", () => {
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
    await waitFor(() => {
      expect(screen.getByTestId("org-group-filter")).toHaveAttribute("data-value", "1");
    });
    expect(screen.getByTestId("org-unit-filter")).toHaveAttribute("data-value", "44");
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
