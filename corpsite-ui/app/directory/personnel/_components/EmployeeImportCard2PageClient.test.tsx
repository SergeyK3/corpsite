import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EmployeeImportCard2PageClient from "./EmployeeImportCard2PageClient";

const getEmployeeMock = vi.fn();
const getEmployeeImportCard2OptionalMock = vi.fn();
const getPprByEmployeeIdMock = vi.fn();

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
}));

vi.mock("../_lib/pprQueryApi.client", () => ({
  getPprByEmployeeId: (...args: unknown[]) => getPprByEmployeeIdMock(...args),
}));

vi.mock("./EmployeeOperationalAssignmentSection", () => ({ default: () => <div /> }));
vi.mock("./EmployeePersonnelHistorySection", () => ({ default: () => <div /> }));
vi.mock("./EmployeeCardGeneralSection", () => ({ default: () => <div /> }));
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
    getEmployeeMock.mockResolvedValue({ employee_id: 228, fio: "Умерзакова Махаббат Тылеулесовна" });
    getEmployeeImportCard2OptionalMock.mockResolvedValue(null);
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
});