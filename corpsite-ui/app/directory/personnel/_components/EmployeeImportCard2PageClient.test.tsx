import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EmployeeImportCard2PageClient from "./EmployeeImportCard2PageClient";

const getEmployeeMock = vi.fn();
const getEmployeeImportCard2OptionalMock = vi.fn();
const getPprByEmployeeIdMock = vi.fn();
const apiAuthMeMock = vi.fn();
const listNormalizedRecordsMock = vi.fn();
const runPersonLinkPreflightMock = vi.fn();

vi.mock("@/lib/api", () => ({ apiAuthMe: () => apiAuthMeMock() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("../../employees/_lib/api.client", () => ({
  getEmployee: (...args: unknown[]) => getEmployeeMock(...args),
  mapApiErrorToMessage: () => "Ошибка загрузки",
}));

vi.mock("../_lib/importApi.client", () => ({
  getEmployeeImportCard2Optional: (...args: unknown[]) => getEmployeeImportCard2OptionalMock(...args),
  listNormalizedRecords: (...args: unknown[]) => listNormalizedRecordsMock(...args),
}));
vi.mock("../_lib/personnelMigrationApi.client", () => ({ runPersonLinkPreflight: (...args: unknown[]) => runPersonLinkPreflightMock(...args) }));
vi.mock("./PersonLinkDialog", () => ({ default: () => <div data-testid="person-link-dialog" /> }));

vi.mock("../_lib/pprQueryApi.client", () => ({
  getPprByEmployeeId: (...args: unknown[]) => getPprByEmployeeIdMock(...args),
}));

vi.mock("./EmployeeOperationalAssignmentSection", () => ({
  default: ({ onAssignmentChanged }: { onAssignmentChanged?: () => void }) => (
    <button type="button" data-testid="assignment-changed" onClick={() => onAssignmentChanged?.()} />
  ),
}));
vi.mock("./EmployeePersonnelHistorySection", () => ({ default: () => <div /> }));
vi.mock("./EmployeeCardGeneralSection", () => ({
  default: ({ details }: { details: { position?: { name?: string | null }; status?: string } }) => (
    <>
      <div data-testid="general-position">{details.position?.name ?? "—"}</div>
      <div data-testid="general-status">{details.status ?? "—"}</div>
    </>
  ),
}));
vi.mock("./EmployeeCardOrdersSection", () => ({ default: () => <div /> }));
vi.mock("./EmployeeCardDeletionNotice", () => ({ default: () => <div /> }));
vi.mock("./EmployeeImportCardSection", () => ({
  EmployeeImportCardSection: ({ children }: { children: React.ReactNode }) => <section>{children}</section>,
  EmployeeImportCardSectionNav: () => <nav />,
}));
vi.mock("../../employees/_components/EmployeeAccountSections", () => ({ default: () => <div /> }));

describe("EmployeeImportCard2PageClient", () => {
  beforeEach(() => {
    getEmployeeMock.mockReset();
    getEmployeeImportCard2OptionalMock.mockReset();
    getPprByEmployeeIdMock.mockReset();
    apiAuthMeMock.mockResolvedValue({ has_hr_enrollment_manager: true });
    listNormalizedRecordsMock.mockResolvedValue({ items: [{ employee_id: 228, iin: "851101300451", review_status: "approved", batch_id: 1, row_id: 2, normalized_record_id: 3 }] });
    runPersonLinkPreflightMock.mockResolvedValue({ blockers: [], expected_precondition: "x" });
    getEmployeeMock.mockResolvedValue({ employee_id: 228, fio: "Умерзакова Махаббат Тылеулесовна" });
    getEmployeeImportCard2OptionalMock.mockResolvedValue(null);
  });

  it("shows Person-link CTA only when person_id is null and opens the dialog", async () => {
    render(<EmployeeImportCard2PageClient employeeId="228" />);
    const button = await screen.findByRole("button", { name: "Создать рабочую личную карточку" });
    fireEvent.click(button);
    expect(await screen.findByTestId("person-link-dialog")).toBeInTheDocument();
  });

  it("hides Person-link CTA when employee already has person_id", async () => {
    getEmployeeMock.mockResolvedValue({ employee_id: 228, fio: "Employee", person_id: 99 });
    render(<EmployeeImportCard2PageClient employeeId="228" />);
    await screen.findByRole("heading", { name: "Employee" });
    expect(screen.queryByRole("button", { name: "Создать рабочую личную карточку" })).toBeNull();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("opens an operational employee without Person through the operational API only", async () => {
    render(<EmployeeImportCard2PageClient employeeId="228" />);

    expect(await screen.findByRole("heading", { name: "Умерзакова Махаббат Тылеулесовна" })).toBeInTheDocument();
    await waitFor(() => {
      expect(getEmployeeMock).toHaveBeenCalledWith("228");
      expect(getEmployeeImportCard2OptionalMock).toHaveBeenCalledWith("228");
    });
    expect(getPprByEmployeeIdMock).not.toHaveBeenCalled();
  });

  it("reloads the card shell with the corrected position after assignment correction", async () => {
    getEmployeeMock
      .mockResolvedValueOnce({
        employee_id: 228,
        fio: "Шаймарданова Алия",
        position: { id: 501, name: "Менеджер" },
      })
      .mockResolvedValueOnce({
        employee_id: 228,
        fio: "Шаймарданова Алия",
        position: { id: 502, name: "Референт" },
      });

    render(<EmployeeImportCard2PageClient employeeId="228" />);

    expect(await screen.findByTestId("general-position")).toHaveTextContent("Менеджер");
    fireEvent.click(screen.getByTestId("assignment-changed"));

    await waitFor(() => {
      expect(getEmployeeMock).toHaveBeenCalledTimes(2);
      expect(screen.getByTestId("general-position")).toHaveTextContent("Референт");
    });
  });
  it("reloads the card shell with the corrected status", async () => {
    getEmployeeMock
      .mockResolvedValueOnce({ employee_id: 228, fio: "Достоярова", status: "active" })
      .mockResolvedValueOnce({ employee_id: 228, fio: "Достоярова", status: "inactive" });

    render(<EmployeeImportCard2PageClient employeeId="228" />);

    expect(await screen.findByTestId("general-status")).toHaveTextContent("active");
    fireEvent.click(screen.getByTestId("assignment-changed"));

    await waitFor(() => {
      expect(getEmployeeMock).toHaveBeenCalledTimes(2);
      expect(screen.getByTestId("general-status")).toHaveTextContent("inactive");
    });
  });
});
