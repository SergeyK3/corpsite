import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EmployeesPageClient from "./EmployeesPageClient";
import { OPEN_PERSONAL_CARD_CTA } from "@/lib/personnelCardTerminology";

const pushMock = vi.fn();
const replaceMock = vi.fn();

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
    items: [{ employee_id: 42, fio: "Иванов Иван", status: "active", employment_rate: 1 }],
    total: 1,
  })),
  getPositions: vi.fn(async () => ({ items: [] })),
  getDepartments: vi.fn(async () => ({ items: [] })),
  mapApiErrorToMessage: (e: unknown) => String(e),
  createEmployee: vi.fn(),
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
    items: [{ employee_id: 42, fio: "Иванов Иван", status: "active", employment_rate: 1 }],
    total: 1,
  },
  initialError: null,
  refreshResetsOrgUnitFilter: true,
};

beforeEach(() => {
  pushMock.mockReset();
  replaceMock.mockReset();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("EmployeesPageClient staff canonical navigation", () => {
  it("does not render working drawer on /directory/staff", async () => {
    render(<EmployeesPageClient {...baseProps} />);

    expect(await screen.findByRole("link", { name: OPEN_PERSONAL_CARD_CTA })).toBeInTheDocument();
    expect(screen.queryByTestId("employee-drawer")).not.toBeInTheDocument();
  });

  it("shows only one «Открыть» action linking to PPR card", async () => {
    render(<EmployeesPageClient {...baseProps} />);

    const links = await screen.findAllByRole("link", { name: OPEN_PERSONAL_CARD_CTA });
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute("href", "/directory/personnel/employees/42/card");
    expect(screen.queryByText("Карточка")).not.toBeInTheDocument();
  });

  it("never mounts drawer shell on staff page", async () => {
    render(<EmployeesPageClient {...baseProps} />);

    await screen.findByRole("link", { name: OPEN_PERSONAL_CARD_CTA });
    expect(screen.queryByTestId("employee-drawer")).not.toBeInTheDocument();
    expect(screen.queryByText("Карточка")).not.toBeInTheDocument();
  });
});
