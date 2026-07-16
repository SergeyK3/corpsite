import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import OrgUnitScopeFilter from "@/components/OrgUnitScopeFilter";
import { loadOrgUnitSelectOptions } from "@/lib/orgUnitsSelect";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/directory/personnel/orders",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/lib/orgUnitsSelect", () => ({
  loadOrgUnitSelectOptions: vi.fn(),
}));

const clinicalGroupId = 1;
const adminGroupId = 2;

const catalog = [
  { unit_id: 100, name: "Клинический корпус", group_id: clinicalGroupId },
  { unit_id: 101, name: "Терапевтическое отделение", group_id: clinicalGroupId },
  { unit_id: 200, name: "Отдел кадров", group_id: adminGroupId },
  { unit_id: 10, name: "Отделение A", group_id: clinicalGroupId },
  { unit_id: 20, name: "Отделение B", group_id: adminGroupId },
];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("OrgUnitScopeFilter cascade", () => {
  it("filters catalog when group is selected", async () => {
    vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue(catalog);

    render(
      <OrgUnitScopeFilter
        basePath="/directory/personnel/orders"
        label="Подразделение"
        allLabel="Выберите подразделение"
        orgGroupId={clinicalGroupId}
        value={null}
        onChange={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(loadOrgUnitSelectOptions).toHaveBeenCalled();
    });

    expect(await screen.findByRole("option", { name: "Клинический корпус" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Терапевтическое отделение" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Отдел кадров" })).not.toBeInTheDocument();
  });

  it("loads full catalog when org group is not selected", async () => {
    vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue(catalog);

    render(
      <OrgUnitScopeFilter
        basePath="/directory/personnel/orders"
        orgGroupId={null}
        value={null}
        onChange={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(loadOrgUnitSelectOptions).toHaveBeenCalled();
    });
    expect(await screen.findByRole("option", { name: "Отдел кадров" })).toBeInTheDocument();
  });

  it("replaces dropdown options when org group changes", async () => {
    vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue(catalog);

    const { rerender } = render(
      <OrgUnitScopeFilter
        basePath="/directory/personnel/orders"
        orgGroupId={clinicalGroupId}
        value={null}
        onChange={vi.fn()}
      />,
    );

    expect(await screen.findByRole("option", { name: "Клинический корпус" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Отдел кадров" })).not.toBeInTheDocument();

    rerender(
      <OrgUnitScopeFilter
        basePath="/directory/personnel/orders"
        orgGroupId={adminGroupId}
        value={null}
        onChange={vi.fn()}
      />,
    );

    expect(await screen.findByRole("option", { name: "Отдел кадров" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Клинический корпус" })).not.toBeInTheDocument();
  });

  it("clears incompatible selected unit when group changes", async () => {
    vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue(catalog);
    const onChange = vi.fn();

    const { rerender } = render(
      <OrgUnitScopeFilter
        basePath="/directory/personnel/orders"
        orgGroupId={clinicalGroupId}
        value={101}
        onChange={onChange}
      />,
    );

    await waitFor(() => {
      expect(loadOrgUnitSelectOptions).toHaveBeenCalled();
    });

    rerender(
      <OrgUnitScopeFilter
        basePath="/directory/personnel/orders"
        orgGroupId={adminGroupId}
        value={101}
        onChange={onChange}
      />,
    );

    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith(null);
    });
  });

  it("clears unit pinned only in display options when catalog rejects group pairing", async () => {
    const displayWithHistorical = [
      ...catalog,
      { unit_id: 41, name: "ММЦ (корень)", group_id: clinicalGroupId },
    ];
    const onChange = vi.fn();

    render(
      <OrgUnitScopeFilter
        basePath="/directory/personnel/orders"
        orgGroupId={clinicalGroupId}
        value={41}
        unitOptions={displayWithHistorical}
        catalogUnitOptions={catalog}
        onChange={onChange}
      />,
    );

    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith(null);
    });
  });

  it("calls onChange with selected unit id", async () => {
    vi.mocked(loadOrgUnitSelectOptions).mockResolvedValue(catalog);
    const onChange = vi.fn();

    render(
      <OrgUnitScopeFilter
        basePath="/directory/personnel/orders"
        orgGroupId={clinicalGroupId}
        value={null}
        onChange={onChange}
      />,
    );

    const select = await screen.findByTestId("org-unit-scope-filter-select");
    fireEvent.change(select, { target: { value: "101" } });

    expect(onChange).toHaveBeenCalledWith(101);
  });
});
