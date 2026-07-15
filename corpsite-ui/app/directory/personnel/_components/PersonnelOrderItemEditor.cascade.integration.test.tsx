import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelOrderItemEditor from "./PersonnelOrderItemEditor";
import { loadScopedPositionOptions, loadGlobalPositionCatalogCached } from "@/lib/taskOrgFilters";
import { loadOrgUnitSelectOptions } from "@/lib/orgUnitsSelect";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/directory/personnel/orders",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/lib/orgScope", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/orgScope")>();
  return {
    ...actual,
    fetchDepartmentGroups: vi.fn(async () => [
      { group_id: 1, group_name: "Клинические" },
      { group_id: 2, group_name: "Параклинические" },
      { group_id: 3, group_name: "Административно-хозяйственные" },
    ]),
  };
});

vi.mock("@/app/directory/employees/_lib/api.client", () => ({
  getEmployees: vi.fn(async () => ({ items: [], total: 0 })),
  getEmployee: vi.fn(),
}));

const CLINICAL_GROUP_ID = 1;
const ADMIN_GROUP_ID = 3;

/** Enriched catalog after prepareOrgTree (MMC stripped, group_id inherited). */
const orgUnitCatalog = [
  { unit_id: 42, name: "Стационар 1", group_id: CLINICAL_GROUP_ID },
  { unit_id: 43, name: "Стационар 2", group_id: CLINICAL_GROUP_ID },
  { unit_id: 44, name: "Амбулатория", group_id: CLINICAL_GROUP_ID },
  { unit_id: 73, name: "Отдел кадров", group_id: ADMIN_GROUP_ID },
  { unit_id: 56, name: "Лаборатория", group_id: 2 },
];

vi.mock("@/lib/orgUnitsSelect", () => ({
  loadOrgUnitSelectOptions: vi.fn(async () => orgUnitCatalog),
}));

vi.mock("@/lib/taskOrgFilters", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/taskOrgFilters")>();
  return {
    ...actual,
    loadScopedPositionOptions: vi.fn(async () => []),
    loadGlobalPositionCatalogCached: vi.fn(async () => [
      { id: 501, label: "Врач-терапевт" },
      { id: 502, label: "Медсестра" },
    ]),
  };
});

vi.mock("../_lib/personnelOrdersApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/personnelOrdersApi.client")>();
  return {
    ...actual,
    createPersonnelOrderItem: vi.fn(),
    updatePersonnelOrderItem: vi.fn(),
  };
});

async function selectOrgGroup(groupId: string) {
  const groupSelect = await screen.findByTestId("org-scope-filter-select");
  await waitFor(() => {
    expect(groupSelect).not.toBeDisabled();
  });
  fireEvent.change(groupSelect, { target: { value: groupId } });
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  vi.mocked(loadScopedPositionOptions).mockImplementation(async (scope) => {
    if (scope.org_unit_id === 44) {
      return [{ id: 501, label: "Врач-терапевт" }];
    }
    return [];
  });
});

describe("PersonnelOrderItemEditor cascade integration", () => {
  it("shows clinical subdivisions after group selection and excludes HR department", async () => {
    render(<PersonnelOrderItemEditor orderId={1} orderTypeCode="HIRE" items={[]} onChanged={vi.fn()} />);

    await selectOrgGroup(String(CLINICAL_GROUP_ID));

    await waitFor(() => {
      expect(loadOrgUnitSelectOptions).toHaveBeenCalled();
    });

    const unitSelect = await screen.findByTestId("org-unit-scope-filter-select");
    expect(unitSelect).not.toBeDisabled();
    expect(await screen.findByRole("option", { name: "Амбулатория" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Стационар 1" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Отдел кадров" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Многопрофильный медицинский центр" })).not.toBeInTheDocument();
  });

  it("loads positions after subdivision selection and allows choosing position", async () => {
    render(<PersonnelOrderItemEditor orderId={1} orderTypeCode="HIRE" items={[]} onChanged={vi.fn()} />);

    await selectOrgGroup(String(CLINICAL_GROUP_ID));

    const unitSelect = await screen.findByTestId("org-unit-scope-filter-select");
    fireEvent.change(unitSelect, { target: { value: "44" } });

    await waitFor(() => {
      expect(loadScopedPositionOptions).toHaveBeenCalledWith({
        org_group_id: CLINICAL_GROUP_ID,
        org_unit_id: 44,
        scope: "allowed",
      });
    });

    const positionSelect = screen.getByTestId("personnel-order-position-select");
    await waitFor(() => {
      expect(positionSelect).not.toBeDisabled();
    });

    expect(await screen.findByRole("option", { name: "Врач-терапевт" })).toBeInTheDocument();
    fireEvent.change(positionSelect, { target: { value: "501" } });
    expect(positionSelect).toHaveValue("501");
  });

  it("clears subdivision and position when group changes", async () => {
    render(<PersonnelOrderItemEditor orderId={1} orderTypeCode="HIRE" items={[]} onChanged={vi.fn()} />);

    await selectOrgGroup(String(CLINICAL_GROUP_ID));

    const unitSelect = await screen.findByTestId("org-unit-scope-filter-select");
    fireEvent.change(unitSelect, { target: { value: "44" } });

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-position-select")).not.toBeDisabled();
    });
    fireEvent.change(screen.getByTestId("personnel-order-position-select"), {
      target: { value: "501" },
    });

    await selectOrgGroup(String(ADMIN_GROUP_ID));

    await waitFor(() => {
      expect(screen.getByTestId("org-unit-scope-filter-select")).toHaveValue("");
      expect(screen.getByTestId("personnel-order-position-select")).toHaveValue("");
    });
    expect(await screen.findByRole("option", { name: "Отдел кадров" })).toBeInTheDocument();
  });

  it("clears position when subdivision changes", async () => {
    render(<PersonnelOrderItemEditor orderId={1} orderTypeCode="HIRE" items={[]} onChanged={vi.fn()} />);

    await selectOrgGroup(String(CLINICAL_GROUP_ID));

    const unitSelect = await screen.findByTestId("org-unit-scope-filter-select");
    fireEvent.change(unitSelect, { target: { value: "44" } });

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-position-select")).not.toBeDisabled();
    });
    fireEvent.change(screen.getByTestId("personnel-order-position-select"), {
      target: { value: "501" },
    });

    fireEvent.change(unitSelect, { target: { value: "42" } });

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-position-select")).toHaveValue("");
    });
  });

  it("does not leave subdivision select empty when clinical group has units", async () => {
    render(<PersonnelOrderItemEditor orderId={1} orderTypeCode="HIRE" items={[]} onChanged={vi.fn()} />);

    await selectOrgGroup(String(CLINICAL_GROUP_ID));

    await waitFor(() => {
      const unitSelect = screen.getByTestId("org-unit-scope-filter-select") as HTMLSelectElement;
      expect(unitSelect.options.length).toBeGreaterThan(1);
    });
  });
});
