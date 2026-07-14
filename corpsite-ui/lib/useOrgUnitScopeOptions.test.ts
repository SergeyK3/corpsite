import { describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import { useOrgUnitScopeOptions } from "./useOrgUnitScopeOptions";
import { loadOrgUnitSelectOptions } from "./orgUnitsSelect";

vi.mock("./orgUnitsSelect", () => ({
  loadOrgUnitSelectOptions: vi.fn(),
}));

const catalog = [
  { unit_id: 100, name: "Клинический корпус", group_id: 1 },
  { unit_id: 101, name: "Терапевтическое отделение", group_id: 1 },
  { unit_id: 200, name: "Отдел кадров", group_id: 2 },
  { unit_id: 10, name: "Отделение A", group_id: 1 },
  { unit_id: 20, name: "Отделение B", group_id: 2 },
];

describe("useOrgUnitScopeOptions", () => {
  it("filters catalog when group is selected", async () => {
    vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue(catalog);

    const { result } = renderHook(() => useOrgUnitScopeOptions(1));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(loadOrgUnitSelectOptions).toHaveBeenCalledTimes(1);
    expect(result.current.options.map((row) => row.unit_id).sort((a, b) => a - b)).toEqual([
      10, 100, 101,
    ]);
    expect(result.current.options.some((row) => row.name === "Отдел кадров")).toBe(false);
  });

  it("returns full catalog when group is not selected", async () => {
    vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue(catalog);

    const { result } = renderHook(() => useOrgUnitScopeOptions(null));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.options).toHaveLength(catalog.length);
  });

  it("recomputes filtered options when group id changes without extra fetch", async () => {
    vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue(catalog);

    const { result, rerender } = renderHook(({ groupId }: { groupId: number | null }) =>
      useOrgUnitScopeOptions(groupId),
    { initialProps: { groupId: 1 as number | null } });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.options.map((row) => row.unit_id).sort((a, b) => a - b)).toEqual([
      10, 100, 101,
    ]);

    vi.mocked(loadOrgUnitSelectOptions).mockClear();
    rerender({ groupId: 2 });

    expect(loadOrgUnitSelectOptions).not.toHaveBeenCalled();
    expect(result.current.options.map((row) => row.unit_id)).toEqual([200, 20]);
  });

  it("returns empty options for group with no units in scoped catalog", async () => {
    vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue([
      { unit_id: 200, name: "Отдел кадров", group_id: 2 },
    ]);

    const { result } = renderHook(() => useOrgUnitScopeOptions(1));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.options).toEqual([]);
  });

  it("returns org-wide catalog entries for clinical group when HR scope is organization-wide", async () => {
    const orgWideCatalog = [
      { unit_id: 101, name: "Терапевтическое отделение", group_id: 1 },
      { unit_id: 102, name: "Хирургическое отделение", group_id: 1 },
      { unit_id: 200, name: "Отдел кадров", group_id: 2 },
    ];
    vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue(orgWideCatalog);

    const { result } = renderHook(() => useOrgUnitScopeOptions(1));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.options.map((row) => row.unit_id).sort((a, b) => a - b)).toEqual([101, 102]);
    expect(result.current.options.some((row) => row.name === "Отдел кадров")).toBe(false);
  });
});
