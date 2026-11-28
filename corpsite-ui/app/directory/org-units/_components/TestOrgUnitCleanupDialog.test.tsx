import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TestOrgUnitCleanupDialog from "./TestOrgUnitCleanupDialog";

const previewMock = vi.fn();
const deleteMock = vi.fn();
vi.mock("../_lib/api.client", () => ({
  previewTestOrgUnitCleanup: (...args: unknown[]) => previewMock(...args),
  markTestOrgUnit: vi.fn(),
  deleteTestOrgUnit: (...args: unknown[]) => deleteMock(...args),
}));

const preview = {
  unit_id: 41, name: "Учебное подразделение", is_test_marked: true,
  counts: { personnel_order_items: 1, employees: 0 },
  blockers: [], can_delete: true, snapshot_hash: "a".repeat(64),
};

beforeEach(() => {
  previewMock.mockReset().mockResolvedValue(preview);
  deleteMock.mockReset().mockResolvedValue({ audit_id: 1, deleted_counts: { org_units: 1 } });
});
afterEach(cleanup);

describe("test org unit cleanup", () => {
  it("requires the same checkbox before invoking the existing delete API", async () => {
    const onDeleted = vi.fn();
    render(<TestOrgUnitCleanupDialog unitId={41} name={preview.name} onClose={vi.fn()} onDeleted={onDeleted} />);
    const checkbox = await screen.findByRole("checkbox", { name: "Подтверждаю окончательное удаление" });
    const button = screen.getByRole("button", { name: "Удалить окончательно" });
    expect(checkbox).not.toBeChecked();
    expect(button).toBeDisabled();
    fireEvent.click(checkbox);
    expect(button).toBeEnabled();
    fireEvent.click(button);
    await waitFor(() => expect(deleteMock).toHaveBeenCalledWith(41, preview.snapshot_hash));
    expect(onDeleted).toHaveBeenCalled();
  });

  it("keeps deletion blocked even when the checkbox is checked", async () => {
    previewMock.mockResolvedValue({ ...preview, can_delete: false, blockers: ["Связанные сотрудники: 1"] });
    render(<TestOrgUnitCleanupDialog unitId={41} name={preview.name} onClose={vi.fn()} onDeleted={vi.fn()} />);
    fireEvent.click(await screen.findByRole("checkbox"));
    expect(screen.getByRole("button", { name: "Удалить окончательно" })).toBeDisabled();
    expect(deleteMock).not.toHaveBeenCalled();
  });

  it("refreshes changed dependencies and clears confirmation after a rejected delete", async () => {
    previewMock.mockReset()
      .mockResolvedValueOnce(preview)
      .mockResolvedValueOnce({ ...preview, snapshot_hash: "b".repeat(64), counts: { employees: 1 },
        blockers: ["Связанные сотрудники: 1"], can_delete: false });
    deleteMock.mockRejectedValue(new Error("Состав зависимостей изменился"));
    render(<TestOrgUnitCleanupDialog unitId={41} name={preview.name} onClose={vi.fn()} onDeleted={vi.fn()} />);
    const checkbox = await screen.findByRole("checkbox");
    fireEvent.click(checkbox);
    fireEvent.click(screen.getByRole("button", { name: "Удалить окончательно" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Состав зависимостей изменился");
    await waitFor(() => expect(checkbox).not.toBeChecked());
    expect(screen.getByRole("button", { name: "Удалить окончательно" })).toBeDisabled();
    expect(previewMock).toHaveBeenCalledTimes(2);
  });
});
