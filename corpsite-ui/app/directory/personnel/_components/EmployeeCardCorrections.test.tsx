import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EmployeeCardGeneralSection from "./EmployeeCardGeneralSection";
import EmployeeOperationalAssignmentSection from "./EmployeeOperationalAssignmentSection";
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
    allOptions: [{ id: 501, label: "Врач-терапевт" }],
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
  it("does not render the separate general correction action", () => {
    render(<EmployeeCardGeneralSection employeeId="1" details={employeeDetails} />);
    expect(screen.queryByTestId("general-correction-open")).not.toBeInTheDocument();
    expect(screen.queryByTestId("general-correction-drawer")).not.toBeInTheDocument();
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
    expect(screen.queryByText("Оформить новое назначение")).not.toBeInTheDocument();
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

    fireEvent.change(screen.getByTestId("assignment-correction-status"), {
      target: { value: "inactive" },
    });
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
          domain: "combined",
          status: "inactive",
          reason: "Ошибка импорта",
          comment: "Сверка",
        }),
      );
    });
    expect(onAssignmentChanged).toHaveBeenCalled();
  });

  it("submits changed general, assignment, and status values in one combined request", async () => {
    vi.mocked(correctEmployee).mockResolvedValue({ item: employeeDetails, event: {} as never });
    render(<EmployeeOperationalAssignmentSection employeeId="1" batchId={7} onAssignmentChanged={vi.fn()} />);

    await waitFor(() => screen.getByTestId("assignment-correction-open"));
    fireEvent.click(screen.getByTestId("assignment-correction-open"));
    await waitFor(() => screen.getByTestId("assignment-correction-drawer"));
    fireEvent.change(screen.getByTestId("assignment-correction-full-name"), { target: { value: "Иванов И. И." } });
    fireEvent.change(screen.getByTestId("assignment-correction-rate"), { target: { value: "0.5" } });
    fireEvent.change(screen.getByTestId("assignment-correction-status"), { target: { value: "inactive" } });
    fireEvent.change(screen.getByTestId("assignment-correction-reason"), { target: { value: "Сверка" } });
    fireEvent.change(screen.getByTestId("assignment-correction-comment"), { target: { value: "Подтверждено" } });
    fireEvent.click(screen.getByTestId("assignment-correction-submit"));

    await waitFor(() => expect(correctEmployee).toHaveBeenCalledTimes(1));
    expect(vi.mocked(correctEmployee)).toHaveBeenCalledWith("1", expect.objectContaining({
      domain: "combined", full_name: "Иванов И. И.", employment_rate: 0.5, status: "inactive",
    }));
    expect(vi.mocked(correctEmployee).mock.calls[0]?.[1]).not.toHaveProperty("org_unit_id");
    expect(vi.mocked(correctEmployee).mock.calls[0]?.[1]).not.toHaveProperty("position_id");
  });

  it("keeps the drawer open and does not refresh the card after a failed request", async () => {
    vi.mocked(correctEmployee).mockRejectedValue(new Error("save failed"));
    const onAssignmentChanged = vi.fn();
    render(<EmployeeOperationalAssignmentSection employeeId="1" batchId={7} onAssignmentChanged={onAssignmentChanged} />);
    await waitFor(() => screen.getByTestId("assignment-correction-open"));
    fireEvent.click(screen.getByTestId("assignment-correction-open"));
    await waitFor(() => screen.getByTestId("assignment-correction-drawer"));
    fireEvent.change(screen.getByTestId("assignment-correction-status"), { target: { value: "inactive" } });
    fireEvent.change(screen.getByTestId("assignment-correction-reason"), { target: { value: "Сверка" } });
    fireEvent.change(screen.getByTestId("assignment-correction-comment"), { target: { value: "Подтверждено" } });
    fireEvent.click(screen.getByTestId("assignment-correction-submit"));

    expect(await screen.findByText("save failed")).toBeInTheDocument();
    expect(screen.getByTestId("assignment-correction-drawer")).toBeInTheDocument();
    expect(onAssignmentChanged).not.toHaveBeenCalled();
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
    expect(screen.getByText("Исправить ошибку в назначении")).toBeInTheDocument();
    expect(screen.getByTestId("assignment-correction-status")).toHaveValue("active");
    expect(screen.getByTestId("assignment-correction-full-name")).toHaveValue("Иванов Иван Иванович");
  });

  it("does not submit an unchanged status", async () => {
    const onSubmit = vi.fn();
    render(
      <EmployeeAssignmentCorrectionDrawer
        open
        details={employeeDetails}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await waitFor(() => screen.getByTestId("assignment-correction-status"));
    fireEvent.change(screen.getByTestId("assignment-correction-reason"), {
      target: { value: "Проверка без изменения статуса" },
    });
    fireEvent.change(screen.getByTestId("assignment-correction-comment"), {
      target: { value: "Статус подтверждён" },
    });
    fireEvent.click(screen.getByTestId("assignment-correction-submit"));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0]?.[0]).not.toHaveProperty("status");
  });
});

describe("EmployeeOperationalAssignmentSection corrected position", () => {
  it("renders the corrected position after reloading assignment data", async () => {
    const correctedDetails = {
      ...employeeDetails,
      position: { id: 502, name: "Референт" },
    } as EmployeeDetails;
    vi.mocked(getEmployee)
      .mockResolvedValueOnce(employeeDetails)
      .mockResolvedValueOnce(correctedDetails);
    vi.mocked(correctEmployee).mockResolvedValue({
      item: correctedDetails,
      event: { event_id: 3, event_type: "CORRECTION" } as never,
    });

    render(<EmployeeOperationalAssignmentSection employeeId="1" batchId={7} onAssignmentChanged={vi.fn()} />);

    await waitFor(() => screen.getByTestId("assignment-correction-open"));
    fireEvent.click(screen.getByTestId("assignment-correction-open"));
    await waitFor(() => screen.getByTestId("assignment-correction-drawer"));
    fireEvent.change(screen.getByTestId("assignment-correction-status"), {
      target: { value: "inactive" },
    });
    fireEvent.change(screen.getByTestId("assignment-correction-reason"), {
      target: { value: "Ошибка исходных данных" },
    });
    fireEvent.change(screen.getByTestId("assignment-correction-comment"), {
      target: { value: "Проверено" },
    });
    fireEvent.click(screen.getByTestId("assignment-correction-submit"));

    expect(await screen.findByText("Референт")).toBeInTheDocument();
    expect(vi.mocked(correctEmployee).mock.calls[0]?.[1]).toHaveProperty("status", "inactive");
  });
});
