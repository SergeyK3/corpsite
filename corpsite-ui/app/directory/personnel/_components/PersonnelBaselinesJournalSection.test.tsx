import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelBaselinesJournalSection from "./PersonnelBaselinesJournalSection";

const { listMonthlyReferenceForkSources, listControlListBaselines, listInitialBaselineSourceSelections, apiAuthMe } = vi.hoisted(() => ({
  listMonthlyReferenceForkSources: vi.fn(),
  listControlListBaselines: vi.fn(),
  listInitialBaselineSourceSelections: vi.fn(),
  apiAuthMe: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ apiAuthMe }));

vi.mock("@/lib/personnelNav", () => ({
  canSeeHrProcessesNav: () => true,
}));

vi.mock("@/lib/adminNav", () => ({
  isPrivilegedOperator: () => false,
}));

vi.mock("../_lib/mrdApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/mrdApi.client")>();
  return { ...actual, listMonthlyReferenceForkSources };
});

vi.mock("../_lib/importApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/importApi.client")>();
  return { ...actual, listControlListBaselines, listInitialBaselineSourceSelections };
});

describe("PersonnelBaselinesJournalSection", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.clearAllMocks();
    apiAuthMe.mockResolvedValue({ user_id: 1, roles: ["personnel_admin"] });
    listControlListBaselines.mockResolvedValue({ items: [] });
    listInitialBaselineSourceSelections.mockResolvedValue({
      items: [{ report_period: "2026-06-01", source_batch_id: 809, import_code: "2606-02", mutable: true }],
    });
    listMonthlyReferenceForkSources.mockResolvedValue({
      items: [
        {
          mrd_id: 2082,
          report_period: "2082-03-01",
          version: 1,
          status: "ACTIVE",
          row_version: 1,
          entry_count: 99,
          forked_from_reference_id: null,
          is_active_for_period: true,
        },
        {
          mrd_id: 7,
          report_period: "2026-07-01",
          version: 1,
          status: "ACTIVE",
          row_version: 1,
          entry_count: 12,
          forked_from_reference_id: null,
          is_active_for_period: true,
        },
      ],
      active_by_period: { "2082-03-01": 2082, "2026-07-01": 7 },
    });
  });

  it("shows only working window periods on 19.07.2026", async () => {
    vi.setSystemTime(new Date(2026, 6, 19));
    render(<PersonnelBaselinesJournalSection embedded />);
    await waitFor(() => expect(screen.getByTestId("mrd-journal-table")).toBeInTheDocument());
    expect(screen.getByText("06.2026")).toBeInTheDocument();
    expect(screen.getByText("07.2026")).toBeInTheDocument();
    expect(screen.getByText("08.2026")).toBeInTheDocument();
    expect(screen.queryByText("2082")).not.toBeInTheDocument();
    expect(screen.queryByText("09.2026")).not.toBeInTheDocument();
    vi.useRealTimers();
  });

  it("does not show period filter or deleted checkbox", async () => {
    render(<PersonnelBaselinesJournalSection embedded />);
    await waitFor(() => expect(screen.getByTestId("mrd-journal-table")).toBeInTheDocument());
    expect(screen.queryByText("Все периоды")).not.toBeInTheDocument();
    expect(screen.queryByText("Показывать удалённые")).not.toBeInTheDocument();
  });

  it("shows create baseline for August and June/July period actions", async () => {
    vi.setSystemTime(new Date(2026, 6, 19));
    render(<PersonnelBaselinesJournalSection embedded />);
    await waitFor(() => expect(screen.getByTestId("mrd-journal-table")).toBeInTheDocument());
    const formInitialLink = screen.getByTestId("journal-form-initial-2026-06");
    expect(formInitialLink).toHaveTextContent("Сформировать эталон");
    expect(formInitialLink).toHaveAttribute("href", expect.stringContaining("batch_id=809"));
    expect(screen.getByTestId("journal-july-blocked-until-june")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Создать эталон" })).toBeInTheDocument();
    expect(screen.queryByText("Создать версию")).not.toBeInTheDocument();
    expect(screen.queryByText("Создать следующий период")).not.toBeInTheDocument();
    vi.useRealTimers();
  });
});
