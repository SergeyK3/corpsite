import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { groupedCleanupCounts, TestCleanupConfirmationCheckbox, useTestCleanupConfirmation } from "./TestCleanupConfirmation";

type Preview = { snapshot_hash: string; counts: Record<string, number>; blockers: string[]; can_delete: boolean };

function Confirm({ preview }: { preview: Preview }) {
  const { confirmed, setConfirmed } = useTestCleanupConfirmation(preview);
  return <>
    <TestCleanupConfirmationCheckbox checked={confirmed} onChange={setConfirmed} />
    <button disabled={!confirmed || !preview.can_delete}>Удалить окончательно</button>
  </>;
}

describe("test cleanup confirmation", () => {
  it("requires an unchecked-by-default checkbox and resets on any preview change", () => {
    const preview = { snapshot_hash: "a", counts: { employees: 1 }, blockers: [], can_delete: true };
    const { rerender, unmount } = render(<Confirm preview={preview} />);
    const checkbox = screen.getByRole("checkbox", { name: "Подтверждаю окончательное удаление" });
    const button = screen.getByRole("button", { name: "Удалить окончательно" });
    expect(checkbox).not.toBeChecked();
    expect(button).toBeDisabled();
    fireEvent.click(checkbox);
    expect(button).toBeEnabled();
    rerender(<Confirm preview={{ ...preview, counts: { employees: 1, employee_documents: 1 } }} />);
    expect(checkbox).not.toBeChecked();
    expect(button).toBeDisabled();
    fireEvent.click(checkbox);
    expect(button).toBeEnabled();
    rerender(<Confirm preview={{ ...preview, blockers: ["Новая зависимость"], can_delete: false }} />);
    expect(checkbox).not.toBeChecked();
    expect(button).toBeDisabled();
    unmount();
    render(<Confirm preview={preview} />);
    expect(screen.getByRole("checkbox")).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Удалить окончательно" })).toBeDisabled();
  });

  it("groups equal labels and keeps technical keys available to the caller", () => {
    const counts = { employees: 1, personnel_record_metadata: 2, ppr_command_executions: 3 };
    expect(groupedCleanupCounts(counts, { employees: "Сотрудники" }, "Другие персональные данные"))
      .toEqual([["Сотрудники", 1], ["Другие персональные данные", 5]]);
    expect(Object.keys(counts)).toContain("ppr_command_executions");
  });
});
