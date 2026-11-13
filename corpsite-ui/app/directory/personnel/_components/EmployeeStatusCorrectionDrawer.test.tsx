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
        fullName="Иванова Анна"
        currentStatus="working"
        currentAssignmentId={17}
        currentRate={1}
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    fireEvent.change(screen.getByTestId("employee-status-correction-select"), {
      target: { value: "not_working" },
    });
    fireEvent.change(screen.getByTestId("employee-status-correction-reason"), {
      target: { value: "Сверка" },
    });
    fireEvent.click(screen.getByTestId("employee-status-correction-submit"));

    expect(onSubmit).toHaveBeenCalledWith({
      status: "not_working",
      expected_assignment_id: 17,
      expected_assignment_rate: 1,
      reason: "Сверка",
      comment: undefined,
    });
    expect(screen.getByTestId("employee-status-correction-fio")).toHaveTextContent("Иванова Анна");
    expect(screen.getByTestId("employee-status-correction-current")).toHaveTextContent("Работает");
  });

  it("shows a clear instruction instead of a disabled submit for the current status", () => {
    const onClose = vi.fn();
    render(
      <EmployeeStatusCorrectionDrawer
        open
        fullName="Иванова"
        currentStatus="not_working"
        currentAssignmentId={17}
        currentRate={1}
        onClose={onClose}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByTestId("employee-status-correction-close-top")).toHaveTextContent("Закрыть");
    expect(screen.getByTestId("employee-status-correction-select-other-status")).toHaveTextContent("Измените статус или ставку");
    expect(screen.queryByTestId("employee-status-correction-submit")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("employee-status-correction-close-top"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("accepts a comma rate without changing status and shows the saved rate on reopen", () => {
    const onSubmit = vi.fn();
    const props = {
      open: true, fullName: "Иванова Анна", currentStatus: "working" as const,
      currentAssignmentId: 17, currentRate: 1, onClose: vi.fn(), onSubmit,
    };
    const { rerender } = render(<EmployeeStatusCorrectionDrawer {...props} />);
    fireEvent.change(screen.getByTestId("employee-status-correction-rate"), { target: { value: "0,75" } });
    fireEvent.change(screen.getByTestId("employee-status-correction-reason"), { target: { value: "Сверка" } });
    fireEvent.click(screen.getByTestId("employee-status-correction-submit"));
    expect(onSubmit).toHaveBeenCalledWith({
      status: "working", expected_assignment_id: 17, expected_assignment_rate: 1,
      employment_rate: 0.75, reason: "Сверка", comment: undefined,
    });
    rerender(<EmployeeStatusCorrectionDrawer {...props} open={false} />);
    rerender(<EmployeeStatusCorrectionDrawer {...props} currentRate={0.75} />);
    expect(screen.getByTestId("employee-status-correction-current-rate")).toHaveTextContent("0.75");
    expect((screen.getByTestId("employee-status-correction-rate") as HTMLInputElement).value).toBe("0.75");
  });

  it("keeps status-only correction available when the assignment link is ambiguous", () => {
    const onSubmit = vi.fn();
    render(<EmployeeStatusCorrectionDrawer open fullName="Иванова Анна"
      currentStatus="not_working" currentAssignmentId={null} currentRate={null}
      onClose={vi.fn()} onSubmit={onSubmit} />);
    expect(screen.getByTestId("employee-status-correction-rate")).toBeDisabled();
    fireEvent.change(screen.getByTestId("employee-status-correction-select"), { target: { value: "working" } });
    fireEvent.change(screen.getByTestId("employee-status-correction-reason"), { target: { value: "Сверка" } });
    fireEvent.click(screen.getByTestId("employee-status-correction-submit"));
    expect(onSubmit).toHaveBeenCalledWith({ status: "working", reason: "Сверка", comment: undefined });
  });
});
