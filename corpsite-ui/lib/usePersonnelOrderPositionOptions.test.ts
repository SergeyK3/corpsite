import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

import {
  loadGlobalPositionCatalogCached,
  loadScopedPositionOptions,
  resetGlobalPositionCatalogCache,
} from "./taskOrgFilters";
import { usePersonnelOrderPositionOptions } from "./usePersonnelOrderPositionOptions";

vi.mock("./taskOrgFilters", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./taskOrgFilters")>();
  return {
    ...actual,
    loadScopedPositionOptions: vi.fn(),
    loadGlobalPositionCatalogCached: vi.fn(),
  };
});

describe("usePersonnelOrderPositionOptions", () => {
  beforeEach(() => {
    resetGlobalPositionCatalogCache();
    vi.mocked(loadGlobalPositionCatalogCached).mockResolvedValue([
      { id: 1, label: "Дворник" },
      { id: 2, label: "Заведующий" },
      { id: 3, label: "Кадровый специалист" },
      { id: 4, label: "Врач" },
      { id: 5, label: "Медсестра" },
    ]);
    vi.mocked(loadScopedPositionOptions).mockResolvedValue([
      { id: 1, label: "Дворник" },
      { id: 2, label: "Заведующий" },
    ]);
  });

  it("merges scoped and global options with scoped group first", async () => {
    const { result } = renderHook(() =>
      usePersonnelOrderPositionOptions({
        enabled: true,
        orgUnitId: 55,
        orgGroupId: 1,
      }),
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.allOptions.map((row) => row.id)).toEqual([1, 2, 4, 3, 5]);
    expect(result.current.positionGroups[0]?.items.map((row) => row.id)).toEqual([1, 2]);
    expect(result.current.positionGroups[1]?.items.map((row) => row.id)).toEqual([4, 3, 5]);
  });

  it("reloads scoped positions on unit change without reloading global catalog", async () => {
    const { result, rerender } = renderHook(
      ({ orgUnitId }: { orgUnitId: number | null }) =>
        usePersonnelOrderPositionOptions({
          enabled: true,
          orgUnitId,
          orgGroupId: 1,
        }),
      { initialProps: { orgUnitId: 55 as number | null } },
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    const globalCallsAfterMount = vi.mocked(loadGlobalPositionCatalogCached).mock.calls.length;
    const scopedCallsAfterMount = vi.mocked(loadScopedPositionOptions).mock.calls.length;
    expect(globalCallsAfterMount).toBeGreaterThanOrEqual(1);
    expect(scopedCallsAfterMount).toBeGreaterThanOrEqual(1);

    vi.mocked(loadScopedPositionOptions).mockResolvedValueOnce([{ id: 86, label: "Руководитель отдела кадров" }]);
    rerender({ orgUnitId: 73 });

    await waitFor(() => {
      expect(loadScopedPositionOptions.mock.calls.length).toBe(scopedCallsAfterMount + 1);
    });
    expect(vi.mocked(loadGlobalPositionCatalogCached).mock.calls.length).toBe(globalCallsAfterMount);
  });
});
