import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EmployeeStatusCorrectionDrawer from "./EmployeeStatusCorrectionDrawer";

describe("EmployeeStatusCorrectionDrawer", () => {
  afterEach(cleanup);

  it("submits an order-free not-working correction with optional notes", () => {
    const onSubmit = vi.fn();
    render(
      <EmployeeStatusCorrectionDrawer
        open
        fullName="?????????? ????"
        currentStatus="working"
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(screen.getByTestId("employee-status-correction-select"), {
      target: { value: "not_working" },
    });
    fireEvent.change(screen.getByTestId("employee-status-correction-reason"), {
      target: { value: "??????" },
    });
    fireEvent.click(screen.getByTestId("employee-status-correction-submit"));

    expect(onSubmit).toHaveBeenCalledWith({
      status: "not_working",
      reason: "??????",
      comment: undefined,
    });
    expect(screen.getByTestId("employee-status-correction-fio")).toHaveTextContent("?????????? ????");
    expect(screen.getByTestId("employee-status-correction-current")).toHaveTextContent("????????");
  });

  it("shows a clear instruction instead of a disabled submit for the current status", () => {
    const onClose = vi.fn();
    render(
      <EmployeeStatusCorrectionDrawer
        open
        fullName="?????????"
        currentStatus="not_working"
        onClose={onClose}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByTestId("employee-status-correction-close-top")).toHaveTextContent("???????");
    expect(screen.getByTestId("employee-status-correction-select-other-status")).toHaveTextContent("???????? ?????? ??????");
    expect(screen.queryByTestId("employee-status-correction-submit")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("employee-status-correction-close-top"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
