import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ImportMonthlyDiffRemovedSection from "./ImportMonthlyDiffRemovedSection";
import {
  REMOVED_ENTRY_CONFIRM_REMOVAL_LABEL,
  REMOVED_ENTRY_DECISION_FOUNDATION_NOTE,
  REMOVED_ENTRY_RESTORE_LABEL,
} from "../_lib/importRemovedEntryDecisions";
import type { MonthlyDiffRemoval } from "../_lib/importApi.client";

const SAMPLE_REMOVAL: MonthlyDiffRemoval = {
  removal_id: 1,
  canonical_entry_id: 42,
  match_key: "person:1",
  record_kind: "education",
  diff_status: "REMOVED",
  payload: { title: "Высшее образование" },
};

describe("ImportMonthlyDiffRemovedSection", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders recommended step and decision actions for each removed row", () => {
    render(<ImportMonthlyDiffRemovedSection items={[SAMPLE_REMOVAL]} />);

    expect(screen.getByText(/Запись есть в эталоне/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: REMOVED_ENTRY_RESTORE_LABEL })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: REMOVED_ENTRY_CONFIRM_REMOVAL_LABEL })).toBeInTheDocument();
  });

  it("opens explanatory dialog without persisting when decisions are disabled", () => {
    render(<ImportMonthlyDiffRemovedSection items={[SAMPLE_REMOVAL]} />);

    fireEvent.click(screen.getByTestId("removed-entry-restore-42-person:1"));

    expect(screen.getByTestId("removed-entry-decision-dialog")).toBeInTheDocument();
    expect(screen.getByText(REMOVED_ENTRY_DECISION_FOUNDATION_NOTE)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Понятно" })).toBeInTheDocument();
  });

  it("calls onDecision when decisions are enabled", async () => {
    const onDecision = vi.fn();
    render(
      <ImportMonthlyDiffRemovedSection
        items={[SAMPLE_REMOVAL]}
        decisionsEnabled
        onDecision={onDecision}
      />,
    );

    fireEvent.click(screen.getByTestId("removed-entry-confirm_removal-42-person:1"));
    fireEvent.click(screen.getByTestId("removed-entry-decision-confirm"));

    expect(onDecision).toHaveBeenCalledWith(SAMPLE_REMOVAL, "confirm_removal");
    await waitFor(() => {
      expect(screen.queryByTestId("removed-entry-decision-dialog")).not.toBeInTheDocument();
    });
  });
});
