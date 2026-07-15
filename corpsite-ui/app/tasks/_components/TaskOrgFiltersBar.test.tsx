import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import TaskOrgFiltersBar from "@/components/TaskOrgFiltersBar";
import { loadScopedPositionOptions } from "@/lib/taskOrgFilters";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/tasks",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/components/OrgScopeFilter", () => ({
  default: () => <div data-testid="org-scope-filter-stub">OrgScopeFilter</div>,
}));

vi.mock("@/lib/orgUnitsSelect", () => ({
  loadOrgUnitSelectOptions: vi.fn(async () => [
    { unit_id: 10, name: "Отдел A", group_id: 1 },
  ]),
}));

vi.mock("@/lib/taskOrgFilters", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/taskOrgFilters")>();
  return {
    ...actual,
    loadScopedPositionOptions: vi.fn(async () => [{ id: 5, label: "Врач" }]),
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("TaskOrgFiltersBar", () => {
  it("renders interconnected filters for team scope", () => {
    render(<TaskOrgFiltersBar visible />);

    expect(screen.getByTestId("task-org-filters")).toBeInTheDocument();
    expect(screen.getByTestId("org-scope-filter-stub")).toBeInTheDocument();
    expect(screen.getByTestId("task-org-filter-unit")).toBeInTheDocument();
    expect(screen.getByTestId("task-org-filter-position")).toBeInTheDocument();
    expect(screen.queryByTestId("task-org-filter-reset")).not.toBeInTheDocument();
  });

  it("does not render when hidden", () => {
    render(<TaskOrgFiltersBar visible={false} />);
    expect(screen.queryByTestId("task-org-filters")).not.toBeInTheDocument();
  });

  it("loads positions with scope=used", async () => {
    render(<TaskOrgFiltersBar visible />);

    await waitFor(() => {
      expect(loadScopedPositionOptions).toHaveBeenCalled();
    });

    expect(loadScopedPositionOptions).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "used" }),
    );
  });
});
