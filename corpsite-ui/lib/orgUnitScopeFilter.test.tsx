import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import OrgUnitScopeFilter from "@/components/OrgUnitScopeFilter";
import { getOrgUnitsTree } from "@/app/directory/org-units/_lib/api.client";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/directory/personnel/orders",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/app/directory/org-units/_lib/api.client", () => ({
  getOrgUnitsTree: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("OrgUnitScopeFilter", () => {
  it("loads units via getOrgUnitsTree with org_group_id when group is selected", async () => {
    vi.mocked(getOrgUnitsTree).mockResolvedValue({
      items: [
        {
          id: "10",
          unit_id: 10,
          name: "MMC",
          group_id: 1,
          children: [
            {
              id: "11",
              unit_id: 11,
              name: "HR Department",
              group_id: null,
              children: [],
            },
          ],
        },
      ],
      inactive_ids: [],
      root_id: 10,
    });

    render(
      <OrgUnitScopeFilter
        basePath="/directory/personnel/orders"
        label="Подразделение"
        allLabel="Выберите подразделение"
        orgGroupId={1}
        value={null}
        onChange={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(getOrgUnitsTree).toHaveBeenCalledWith({ org_group_id: 1 });
    });

    expect(await screen.findByRole("option", { name: "MMC" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /HR Department/ })).toBeInTheDocument();
  });

  it("loads full tree when org group is not selected", async () => {
    vi.mocked(getOrgUnitsTree).mockResolvedValue({
      items: [
        {
          id: "10",
          unit_id: 10,
          name: "MMC",
          group_id: 1,
          children: [],
        },
      ],
      inactive_ids: [],
      root_id: 10,
    });

    render(
      <OrgUnitScopeFilter
        basePath="/directory/personnel/orders"
        orgGroupId={null}
        value={null}
        onChange={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(getOrgUnitsTree).toHaveBeenCalledWith({ org_group_id: undefined });
    });
    expect(await screen.findByRole("option", { name: "MMC" })).toBeInTheDocument();
  });

  it("replaces dropdown options when org group changes", async () => {
    vi.mocked(getOrgUnitsTree).mockImplementation(async (args) => {
      const groupId = args?.org_group_id;
      if (groupId === 2) {
        return {
          items: [{ id: "20", unit_id: 20, name: "Group 2 Unit", group_id: 2, children: [] }],
          inactive_ids: [],
          root_id: 20,
        };
      }
      return {
        items: [{ id: "10", unit_id: 10, name: "Group 1 Unit", group_id: 1, children: [] }],
        inactive_ids: [],
        root_id: 10,
      };
    });

    const { rerender } = render(
      <OrgUnitScopeFilter
        basePath="/directory/personnel/orders"
        orgGroupId={1}
        value={null}
        onChange={vi.fn()}
      />,
    );

    expect(await screen.findByRole("option", { name: "Group 1 Unit" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Group 2 Unit" })).not.toBeInTheDocument();

    rerender(
      <OrgUnitScopeFilter
        basePath="/directory/personnel/orders"
        orgGroupId={2}
        value={null}
        onChange={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.queryByRole("option", { name: "Group 1 Unit" })).not.toBeInTheDocument();
    });
    expect(await screen.findByRole("option", { name: "Group 2 Unit" })).toBeInTheDocument();
  });
});
