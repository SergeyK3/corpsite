import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EmployeePersonalCardRedirectClient from "./EmployeePersonalCardRedirectClient";

const replaceMock = vi.fn();
const getPprByEmployeeIdMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

vi.mock("../_lib/pprQueryApi.client", () => ({
  getPprByEmployeeId: (...args: unknown[]) => getPprByEmployeeIdMock(...args),
}));

describe("EmployeePersonalCardRedirectClient", () => {
  beforeEach(() => {
    replaceMock.mockReset();
    getPprByEmployeeIdMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("redirects legacy employee route to canonical person card", async () => {
    getPprByEmployeeIdMock.mockResolvedValue({
      identity: { resolved_person_id: 901, requested_employee_id: 55 },
    });

    render(<EmployeePersonalCardRedirectClient employeeId="55" />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/directory/personnel/persons/901/card");
    });
    expect(getPprByEmployeeIdMock).toHaveBeenCalledWith("55", expect.objectContaining({ signal: expect.any(AbortSignal) }));
  });

  it("redirects to canonical person route using resolved person_id", async () => {
    getPprByEmployeeIdMock.mockResolvedValue({
      identity: { resolved_person_id: 501, requested_employee_id: 42 },
    });

    render(
      <EmployeePersonalCardRedirectClient
        employeeId="42"
        legacyQueryString="section=history&return_to=%2Fdirectory%2Fstaff"
      />,
    );

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith(
        "/directory/personnel/persons/501/card?section=history&return_to=%2Fdirectory%2Fstaff",
      );
    });
  });

  it("does not use employee_id as person route key", async () => {
    getPprByEmployeeIdMock.mockResolvedValue({
      identity: { resolved_person_id: 777, requested_employee_id: 42 },
    });

    render(<EmployeePersonalCardRedirectClient employeeId="42" />);

    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalled();
    });
    expect(replaceMock.mock.calls[0]?.[0]).toContain("/persons/777/card");
    expect(replaceMock.mock.calls[0]?.[0]).not.toContain("/persons/42/card");
  });

  it("shows access denied without redirect on 403", async () => {
    getPprByEmployeeIdMock.mockRejectedValue({ status: 403 });

    render(<EmployeePersonalCardRedirectClient employeeId="42" />);

    expect(await screen.findByTestId("employee-card-redirect-error")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("shows not found without redirect on 404", async () => {
    getPprByEmployeeIdMock.mockRejectedValue({ status: 404 });

    render(<EmployeePersonalCardRedirectClient employeeId="42" />);

    expect(await screen.findByTestId("employee-card-redirect-error")).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
