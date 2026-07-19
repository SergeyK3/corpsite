import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ImportRemovalDecisionsPanel from "./ImportRemovalDecisionsPanel";
import type { MonthlyDiffRemoval } from "../_lib/importApi.client";

const sampleItem: MonthlyDiffRemoval = {
  removal_id: 7,
  canonical_entry_id: 42,
  match_key: "person:1",
  record_kind: "roster",
  diff_status: "REMOVED",
  payload: { full_name: "Иванов И.И." },
};

const restoredItem: MonthlyDiffRemoval = {
  ...sampleItem,
  removal_id: 8,
  decision: "restore",
  decided_at: "2026-08-01T10:00:00.000Z",
};

describe("ImportRemovalDecisionsPanel", () => {
  afterEach(() => cleanup());

  it("shows tabs and pending removals by default", () => {
    render(
      <ImportRemovalDecisionsPanel
        pending={[sampleItem]}
        restored={[restoredItem]}
        confirmed={[]}
        decisionsEnabled
        onDecision={vi.fn()}
        onRevert={vi.fn()}
      />,
    );

    expect(screen.getByTestId("removal-decisions-tab-pending")).toHaveTextContent("Ожидают решения (1)");
    expect(screen.getByTestId("removed-entry-restore-42-person:1")).toBeInTheDocument();
  });

  it("switches to restored tab and calls revert", async () => {
    const onRevert = vi.fn().mockResolvedValue(undefined);
    render(
      <ImportRemovalDecisionsPanel
        pending={[]}
        restored={[restoredItem]}
        confirmed={[]}
        decisionsEnabled
        onRevert={onRevert}
      />,
    );

    fireEvent.click(screen.getByTestId("removal-decisions-tab-restored"));
    fireEvent.click(screen.getByTestId("removal-decision-revert-42"));
    fireEvent.click(screen.getByTestId("removal-decision-revert-confirm"));

    await waitFor(() => {
      expect(onRevert).toHaveBeenCalledWith(restoredItem);
    });
  });
});
