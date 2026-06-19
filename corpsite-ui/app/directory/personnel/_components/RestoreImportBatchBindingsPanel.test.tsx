import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import {
  RESTORE_IMPORT_BATCH_BINDINGS_HELP,
  RESTORE_IMPORT_BATCH_BINDINGS_LABEL,
  RestoreImportBatchBindingsPanel,
} from "./RestoreImportBatchBindingsPanel";

const repairBatchEmployeeBindings = vi.fn();

vi.mock("../_lib/importApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/importApi.client")>();
  return {
    ...actual,
    repairBatchEmployeeBindings: (...args: unknown[]) => repairBatchEmployeeBindings(...args),
  };
});

describe("RestoreImportBatchBindingsPanel", () => {
  beforeEach(() => {
    repairBatchEmployeeBindings.mockReset();
    repairBatchEmployeeBindings.mockResolvedValue({
      batch_id: 42,
      rows_processed: 3,
      bound: 2,
      already_bound: 1,
      unbound: 0,
      conflict: 0,
      normalized_records_updated: 2,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("does not render when batch is not selected", () => {
    render(<RestoreImportBatchBindingsPanel batchId={null} />);

    expect(screen.queryByTestId("restore-import-batch-bindings-panel")).not.toBeInTheDocument();
    expect(screen.queryByTestId("restore-import-batch-bindings-button")).not.toBeInTheDocument();
  });

  it("renders batch-scoped restore action when batch is selected", () => {
    render(<RestoreImportBatchBindingsPanel batchId={42} />);

    expect(screen.getByTestId("restore-import-batch-bindings-panel")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: RESTORE_IMPORT_BATCH_BINDINGS_LABEL })).toBeInTheDocument();
    expect(screen.getByText(RESTORE_IMPORT_BATCH_BINDINGS_HELP)).toBeInTheDocument();
    expect(screen.getByTestId("restore-import-batch-bindings-button")).toHaveAttribute("data-batch-id", "42");
  });

  it("calls repair API with selected batch_id only", async () => {
    const onRepaired = vi.fn();

    render(<RestoreImportBatchBindingsPanel batchId={42} onRepaired={onRepaired} />);

    fireEvent.click(screen.getByTestId("restore-import-batch-bindings-button"));

    await waitFor(() => {
      expect(repairBatchEmployeeBindings).toHaveBeenCalledTimes(1);
      expect(repairBatchEmployeeBindings).toHaveBeenCalledWith(42);
    });
    expect(onRepaired).toHaveBeenCalledWith(
      expect.objectContaining({ batch_id: 42, bound: 2 })
    );
  });
});
