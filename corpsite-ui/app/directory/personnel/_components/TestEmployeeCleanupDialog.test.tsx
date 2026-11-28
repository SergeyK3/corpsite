import * as React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import TestEmployeeCleanupDialog from "./TestEmployeeCleanupDialog";
import { previewTestEmployeeCleanup } from "../_lib/personnelLkApi.client";

vi.mock("../_lib/personnelLkApi.client", () => ({
  previewTestEmployeeCleanup: vi.fn(),
  markTestEmployee: vi.fn(),
  markTestPersonnelOrder: vi.fn(),
  deleteTestEmployee: vi.fn(),
  mapPersonnelLkApiError: vi.fn(),
}));

describe("test order confirmation", () => {
  it("uses separate checkboxes and documented evidence without asking for an order number", async () => {
    vi.mocked(previewTestEmployeeCleanup).mockResolvedValue({
      employee_id: 34, person_id: 55, full_name: "Тестовая Майра", login: null,
      is_test_marked: true, counts: {}, retained_counts: {}, blockers: ["Приказы требуют подтверждения"],
      blocker_groups: [], can_delete: false, snapshot_hash: "a".repeat(64), file_count: 0,
      personnel_orders: [
        { order_id: 68, order_number: "ORD-68", order_date: "2026-11-25", order_type_code: "HIRE",
          status: "REGISTERED", item_count: 1, employees: [{ employee_id: 34, full_name: "Тестовая Майра" }],
          signed_copy_count: 0, attachment_count: 0, acknowledgement_count: 0,
          snapshot_hash: "b".repeat(64), is_test_marked: false },
        { order_id: 69, order_number: "ORD-69", order_date: "2026-11-26", order_type_code: "TRANSFER",
          status: "REGISTERED", item_count: 1, employees: [{ employee_id: 34, full_name: "Тестовая Майра" }],
          signed_copy_count: 0, attachment_count: 0, acknowledgement_count: 0,
          snapshot_hash: "c".repeat(64), is_test_marked: false },
        { order_id: 70, order_number: "ORD-70", order_date: "2026-11-27", order_type_code: "HIRE",
          status: "REGISTERED", item_count: 1, employees: [{ employee_id: 34, full_name: "Тестовая Майра" }],
          signed_copy_count: 0, attachment_count: 0, acknowledgement_count: 0,
          snapshot_hash: "d".repeat(64), is_test_marked: true },
      ],
    });
    render(<TestEmployeeCleanupDialog employeeId={34} fullName="Тестовая Майра" mode="delete"
      onClose={vi.fn()} onMarked={vi.fn()} onDeleted={vi.fn()} />);
    await waitFor(() => expect(screen.getAllByLabelText("Подтверждаю тестовое происхождение приказа")).toHaveLength(2));
    expect(screen.queryByLabelText("Введите точный номер приказа")).not.toBeInTheDocument();
    const buttons = screen.getAllByRole("button", { name: "Подтвердить тестовый приказ" });
    expect(buttons).toHaveLength(2);
    expect(buttons[0]).toBeDisabled();
    const evidence = screen.getAllByLabelText("Документированное основание тестового происхождения приказа");
    fireEvent.change(evidence[0], { target: { value: "Отдельный журнал тестового создания приказа" } });
    fireEvent.click(screen.getAllByLabelText("Подтверждаю тестовое происхождение приказа")[0]);
    expect(buttons[0]).toBeEnabled();
    expect(buttons[1]).toBeDisabled();
  });
});
