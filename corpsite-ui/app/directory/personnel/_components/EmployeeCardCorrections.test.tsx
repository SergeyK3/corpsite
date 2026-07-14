import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EmployeeCardGeneralSection from "./EmployeeCardGeneralSection";
import EmployeeOperationalAssignmentSection from "./EmployeeOperationalAssignmentSection";
import EmployeeGeneralCorrectionDrawer from "./EmployeeGeneralCorrectionDrawer";
import EmployeeAssignmentCorrectionDrawer from "./EmployeeAssignmentCorrectionDrawer";
import type { EmployeeDetails } from "../../employees/_lib/types";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/directory/personnel/employees/1/card",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/lib/orgScope", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/orgScope")>();
  return {
    ...actual,
    fetchDepartmentGroups: vi.fn(async () => [{ group_id: 1, group_name: "Клинические" }]),
  };
});

vi.mock("@/app/directory/org-units/_lib/api.client", () => ({
  getOrgUnitsTree: vi.fn(async () => ({
    items: [{ unit_id: 42, name: "Стационар 1", group_id: 1, children: [] }],
  })),
}));

vi.mock("@/lib/useOrgUnitScopeOptions", () => ({
  useOrgUnitScopeOptions: vi.fn(() => ({
    options: [{ unit_id: 42, name: "Стационар 1", group_id: 1 }],
    catalogOptions: [{ unit_id: 42, name: "Стационар 1", group_id: 1 }],
    loading: false,
    error: null,
  })),
}));

vi.mock("@/lib/usePersonnelOrderPositionOptions", () => ({
  usePersonnelOrderPositionOptions: vi.fn(() => ({
    scopedOptions: [{ id: 501, label: "Врач-терапевт" }],
    loading: false,
  })),
}));

vi.mock("../../employees/_lib/api.client", () => ({
  correctEmployee: vi.fn(),
  getEmployee: vi.fn(),
  mapApiErrorToMessage: (e: unknown) => (e instanceof Error ? e.message : "Ошибка"),
}));

vi.mock("../_lib/importApi.client", () => ({
  getNormalizedRecord: vi.fn(),
  listNormalizedRecords: vi.fn(),
  mapImportApiError: (_e: unknown, fallback: string) => fallback,
}));

import { correctEmployee, getEmployee } from "../../employees/_lib/api.client";

const employeeDetails: EmployeeDetails = {
  employee_id: 1,
  fio: "Иванов Иван Иванович",
  status: "active",
  org_unit: { unit_id: 42, name: "Стационар 1" },
  position: { id: 501, name: "Врач-терапевт" },
  rate: 1,
  date_from: "2024-01-15",
  date_to: null,
  is_active: true,
} as EmployeeDetails;

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("EmployeeCardGeneralSection", () => {
  it("opens general correction drawer and submits", async () => {
    vi.mocked(correctEmployee).mockResolvedValue({
      item: { ...employeeDetails, fio: "Иванов И. И." },
      event: { event_id: 1, event_type: "CORRECTION" } as never,
    });

    const onDetailsChanged = vi.fn();
    render(
      <EmployeeCardGeneralSection
        employeeId="1"
        details={employeeDetails}
        onDetailsChanged={onDetailsChanged}
      />,
    );

    fireEvent.click(screen.getByTestId("general-correction-open"));
    expect(screen.getByTestId("general-correction-drawer")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("general-correction-full-name"), {
      target: { value: "Иванов И. И." },
    });
    fireEvent.change(screen.getByTestId("general-correction-reason"), {
      target: { value: "Опечатка" },
    });
    fireEvent.change(screen.getByTestId("general-correction-comment"), {
      target: { value: "По паспорту" },
    });
    fireEvent.click(screen.getByTestId("general-correction-submit"));

    await waitFor(() => {
      expect(correctEmployee).toHaveBeenCalledWith(
        "1",
        expect.objectContaining({
          domain: "general",
          full_name: "Иванов И. И.",
          reason: "Опечатка",
          comment: "По паспорту",
        }),
      );
    });
    expect(onDetailsChanged).toHaveBeenCalled();
  });
});

describe("EmployeeOperationalAssignmentSection", () => {
  beforeEach(() => {
    vi.mocked(getEmployee).mockResolvedValue(employeeDetails);
  });

  it("shows assignment correction button instead of transfer", async () => {
    render(
      <EmployeeOperationalAssignmentSection employeeId="1" batchId={7} onAssignmentChanged={vi.fn()} />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("assignment-correction-open")).toBeInTheDocument();
    });
    expect(screen.queryByText("Изменить назначение")).not.toBeInTheDocument();
  });

  it("submits assignment correction and refreshes", async () => {
    vi.mocked(correctEmployee).mockResolvedValue({
      item: employeeDetails,
      event: { event_id: 2, event_type: "CORRECTION" } as never,
    });

    const onAssignmentChanged = vi.fn();
    render(
      <EmployeeOperationalAssignmentSection
        employeeId="1"
        batchId={7}
        onAssignmentChanged={onAssignmentChanged}
      />,
    );

    await waitFor(() => screen.getByTestId("assignment-correction-open"));
    fireEvent.click(screen.getByTestId("assignment-correction-open"));

    await waitFor(() => screen.getByTestId("assignment-correction-drawer"));

    fireEvent.change(screen.getByTestId("assignment-correction-reason"), {
      target: { value: "Ошибка импорта" },
    });
    fireEvent.change(screen.getByTestId("assignment-correction-comment"), {
      target: { value: "Сверка" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("assignment-correction-submit")).not.toBeDisabled();
    });

    fireEvent.click(screen.getByTestId("assignment-correction-submit"));

    await waitFor(() => {
      expect(correctEmployee).toHaveBeenCalledWith(
        "1",
        expect.objectContaining({
          domain: "assignment",
          org_unit_id: 42,
          reason: "Ошибка импорта",
          comment: "Сверка",
        }),
      );
    });
    expect(onAssignmentChanged).toHaveBeenCalled();
  });
});

describe("EmployeeGeneralCorrectionDrawer", () => {
  it("renders required fields", () => {
    render(
      <EmployeeGeneralCorrectionDrawer
        open
        details={employeeDetails}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByText("Исправить данные")).toBeInTheDocument();
    expect(screen.getByTestId("general-correction-full-name")).toHaveValue("Иванов Иван Иванович");
    expect(screen.getByText("Сохранить корректировку")).toBeInTheDocument();
  });
});

describe("EmployeeAssignmentCorrectionDrawer", () => {
  it("renders org cascade", async () => {
    render(
      <EmployeeAssignmentCorrectionDrawer
        open
        details={employeeDetails}
        onClose={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("assignment-correction-org-cascade")).toBeInTheDocument();
    });
    expect(screen.getByText("Исправить назначение")).toBeInTheDocument();
  });
});
