import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import OrgUnitsAdminClient from "./OrgUnitsAdminClient";

vi.mock("../_lib/adminOrgUnitsApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/adminOrgUnitsApi.client")>();
  return {
    ...actual,
    fetchAdminOrgUnits: vi.fn(),
    fetchAdminOrgUnitDependencies: vi.fn(),
    createAdminOrgUnit: vi.fn(),
    updateAdminOrgUnit: vi.fn(),
    deleteAdminOrgUnit: vi.fn(),
    activateAdminOrgUnit: vi.fn(),
    deactivateAdminOrgUnit: vi.fn(),
    bulkDeleteAdminOrgUnits: vi.fn(),
  };
});

vi.mock("@/lib/orgScope", () => ({
  fetchDepartmentGroups: vi.fn(async () => [
    { group_id: 1, group_name: "Стационар" },
    { group_id: 2, group_name: "Поликлиника" },
  ]),
}));

import {
  activateAdminOrgUnit,
  bulkDeleteAdminOrgUnits,
  createAdminOrgUnit,
  deactivateAdminOrgUnit,
  deleteAdminOrgUnit,
  fetchAdminOrgUnitDependencies,
  fetchAdminOrgUnits,
  mapAdminOrgUnitsApiError,
  SINGLE_ROOT_INVARIANT_MESSAGE,
  updateAdminOrgUnit,
} from "../_lib/adminOrgUnitsApi.client";

const mockedList = vi.mocked(fetchAdminOrgUnits);
const mockedDeps = vi.mocked(fetchAdminOrgUnitDependencies);
const mockedCreate = vi.mocked(createAdminOrgUnit);
const mockedUpdate = vi.mocked(updateAdminOrgUnit);
const mockedDelete = vi.mocked(deleteAdminOrgUnit);
const mockedDeactivate = vi.mocked(deactivateAdminOrgUnit);
const mockedActivate = vi.mocked(activateAdminOrgUnit);
const mockedBulkDelete = vi.mocked(bulkDeleteAdminOrgUnits);

const mmcRoot = {
  unit_id: 10,
  name: "Многопрофильный медицинский центр",
  code: "MMC",
  group_id: 1,
  group_name: "Стационар",
  parent_unit_id: null,
  parent_name: null,
  is_active: true,
  child_count: 2,
  active_employee_count: 0,
};

const sampleUnits = [
  {
    unit_id: 101,
    name: "Тестовое подразделение",
    code: "TST",
    group_id: 1,
    group_name: "Стационар",
    parent_unit_id: 10,
    parent_name: "Многопрофильный медицинский центр",
    is_active: true,
    child_count: 0,
    active_employee_count: 0,
  },
  mmcRoot,
  {
    unit_id: 202,
    name: "Отдел кадров",
    code: "HR",
    group_id: 1,
    group_name: "Стационар",
    parent_unit_id: 10,
    parent_name: "Многопрофильный медицинский центр",
    is_active: false,
    child_count: 1,
    active_employee_count: 5,
  },
];

describe("OrgUnitsAdminClient", () => {
  let unit101Active = true;
  let unit202Active = false;

  function listForParams(params: { status?: string; q?: string } = {}) {
    const all = sampleUnits.map((u) => {
      if (u.unit_id === 101) return { ...u, is_active: unit101Active };
      if (u.unit_id === 202) return { ...u, is_active: unit202Active };
      return u;
    });
    let items = all;
    if (params.status === "active") items = all.filter((u) => u.is_active);
    if (params.status === "inactive") items = all.filter((u) => !u.is_active);
    if (params.q) {
      const q = params.q.toLowerCase();
      items = items.filter(
        (u) =>
          u.name.toLowerCase().includes(q) ||
          String(u.code ?? "").toLowerCase().includes(q) ||
          String(u.unit_id) === q,
      );
    }
    return { items, total: items.length, limit: 500, offset: 0 };
  }

  beforeEach(() => {
    vi.clearAllMocks();
    unit101Active = true;
    unit202Active = false;
    mockedList.mockImplementation(async (params) => listForParams(params ?? {}));
    mockedDeps.mockResolvedValue({ can_delete: true, dependencies: {} });
    mockedCreate.mockResolvedValue({ item: { ...sampleUnits[0], unit_id: 303 } });
    mockedUpdate.mockResolvedValue({ item: { ...sampleUnits[0], name: "Обновлено" } });
    mockedDelete.mockResolvedValue({ ok: true, unit_id: 101 });
    mockedDeactivate.mockImplementation(async (unitId) => {
      if (unitId === 101) unit101Active = false;
      if (unitId === 202) unit202Active = false;
      return { item: { ...sampleUnits[0], unit_id: unitId, is_active: false } };
    });
    mockedActivate.mockImplementation(async (unitId) => {
      if (unitId === 101) unit101Active = true;
      if (unitId === 202) unit202Active = true;
      return { item: { ...sampleUnits[0], unit_id: unitId, is_active: true } };
    });
    mockedBulkDelete.mockResolvedValue({
      results: [
        { unit_id: 101, ok: true },
        {
          unit_id: 202,
          ok: false,
          error_code: "ORG_UNIT_HAS_DEPENDENCIES",
          dependencies: {
            users: 1,
            org_unique_position: 1,
            legacy_position_mapping: 1,
            person_assignments: 1,
          },
        },
      ],
      requested: 2,
      deleted: 1,
      failed: 1,
    });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("uses active status filter by default", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => expect(mockedList).toHaveBeenCalledWith(expect.objectContaining({ status: "active" })));
    const statusSelect = screen.getByTestId("org-units-filter-status") as HTMLSelectElement;
    expect(statusSelect.value).toBe("active");
    expect(screen.getByText("Тестовое подразделение")).toBeInTheDocument();
    expect(screen.queryByText("Отдел кадров")).not.toBeInTheDocument();
  });

  it("switches between active, inactive and all status filters", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-filter-status"));

    fireEvent.change(screen.getByTestId("org-units-filter-status"), { target: { value: "inactive" } });
    await waitFor(() => expect(mockedList).toHaveBeenLastCalledWith(expect.objectContaining({ status: "inactive" })));
    expect(screen.getByText("Отдел кадров")).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("org-units-filter-status"), { target: { value: "all" } });
    await waitFor(() => expect(mockedList).toHaveBeenLastCalledWith(expect.objectContaining({ status: "all" })));
  });

  it("applies debounced search by name", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-filter-search"));
    fireEvent.change(screen.getByTestId("org-units-filter-search"), { target: { value: "Тестовое" } });
    await waitFor(
      () =>
        expect(mockedList).toHaveBeenLastCalledWith(
          expect.objectContaining({ q: "Тестовое", status: "active" }),
        ),
      { timeout: 1000 },
    );
  });

  it("applies debounced search by code and id", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-filter-search"));

    fireEvent.change(screen.getByTestId("org-units-filter-search"), { target: { value: "mmc" } });
    await waitFor(() => expect(mockedList).toHaveBeenLastCalledWith(expect.objectContaining({ q: "mmc" })), {
      timeout: 1000,
    });

    fireEvent.change(screen.getByTestId("org-units-filter-search"), { target: { value: "101" } });
    await waitFor(() => expect(mockedList).toHaveBeenLastCalledWith(expect.objectContaining({ q: "101" })), {
      timeout: 1000,
    });
  });

  it("removes row from active filter after deactivate", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-unit-toggle-active-101"));
    fireEvent.click(screen.getByTestId("org-unit-toggle-active-101"));
    await waitFor(() => expect(mockedDeactivate).toHaveBeenCalledWith(101));
    await waitFor(() => expect(screen.queryByText("Тестовое подразделение")).not.toBeInTheDocument());
  });

  it("shows row again in active filter after activate", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-filter-status"));
    fireEvent.change(screen.getByTestId("org-units-filter-status"), { target: { value: "inactive" } });
    await waitFor(() => screen.getByTestId("org-unit-toggle-active-202"));
    fireEvent.click(screen.getByTestId("org-unit-toggle-active-202"));
    await waitFor(() => expect(mockedActivate).toHaveBeenCalledWith(202));

    fireEvent.change(screen.getByTestId("org-units-filter-status"), { target: { value: "active" } });
    await waitFor(() => expect(screen.getByText("Отдел кадров")).toBeInTheDocument());
  });

  it("renders table with loaded units and group names", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => expect(screen.getByTestId("org-units-table")).toBeInTheDocument());
    expect(screen.getByText("Тестовое подразделение")).toBeInTheDocument();
    expect(screen.getAllByText("Стационар").length).toBeGreaterThan(0);
  });

  it("shows department group names in form while keeping group_id values", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-create-btn"));
    fireEvent.click(screen.getByTestId("org-units-create-btn"));

    const groupSelect = screen.getByTestId("org-unit-form-group") as HTMLSelectElement;
    const options = within(groupSelect).getAllByRole("option");
    expect(options[0]).toHaveTextContent("Стационар");
    expect(options[0]).toHaveValue("1");
    expect(options[1]).toHaveTextContent("Поликлиника");
    expect(options[1]).toHaveValue("2");
  });

  it("hides no-parent option when root exists and defaults parent to MMC", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-create-btn"));
    fireEvent.click(screen.getByTestId("org-units-create-btn"));

    const parentSelect = screen.getByTestId("org-unit-form-parent") as HTMLSelectElement;
    expect(within(parentSelect).queryByText("— корень / без родителя —")).not.toBeInTheDocument();
    expect(parentSelect.value).toBe("10");
  });

  it("does not submit create form without parent when root exists", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-create-btn"));
    fireEvent.click(screen.getByTestId("org-units-create-btn"));

    const parentSelect = screen.getByTestId("org-unit-form-parent") as HTMLSelectElement;
    fireEvent.change(parentSelect, { target: { value: "" } });
    fireEvent.change(screen.getByTestId("org-unit-form-name"), { target: { value: "Новое отделение" } });
    fireEvent.click(screen.getByTestId("org-unit-form-save"));

    await waitFor(() => expect(mockedCreate).not.toHaveBeenCalled());
  });

  it("maps single-root backend error to a readable Russian message", () => {
    const message = mapAdminOrgUnitsApiError(
      {
        status: 400,
        body: { detail: "single-root invariant: root already exists" },
      },
      "fallback",
    );
    expect(message).toBe(SINGLE_ROOT_INVARIANT_MESSAGE);
  });

  it("creates org unit with inherited parent", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-create-btn"));
    fireEvent.click(screen.getByTestId("org-units-create-btn"));
    fireEvent.change(screen.getByTestId("org-unit-form-name"), { target: { value: "Новое отделение" } });
    fireEvent.click(screen.getByTestId("org-unit-form-save"));
    await waitFor(() =>
      expect(mockedCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Новое отделение",
          parent_unit_id: 10,
          group_id: 1,
        }),
      ),
    );
  });

  it("edits org unit", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => expect(screen.getAllByText("Редактировать").length).toBeGreaterThan(0));
    fireEvent.click(screen.getByTestId("org-unit-edit-101"));
    fireEvent.change(screen.getByTestId("org-unit-form-name"), { target: { value: "Обновлено" } });
    fireEvent.click(screen.getByTestId("org-unit-form-save"));
    await waitFor(() => expect(mockedUpdate).toHaveBeenCalledWith(101, expect.any(Object)));
  });

  it("shows dependency dialog with fully localized ordered dependency labels", async () => {
    mockedDeps.mockResolvedValueOnce({
      can_delete: false,
      dependencies: {
        legacy_position_mapping: 1,
        active_employees: 2,
        employees: 5,
        child_org_units: 1,
      },
    });
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-filter-status"));
    fireEvent.change(screen.getByTestId("org-units-filter-status"), { target: { value: "inactive" } });
    await waitFor(() => screen.getByTestId("org-unit-delete-202"));
    fireEvent.click(screen.getByTestId("org-unit-delete-202"));
    await waitFor(() => expect(screen.getByTestId("org-unit-dependency-dialog")).toBeInTheDocument());

    const dialog = within(screen.getByTestId("org-unit-dependency-dialog"));
    const items = dialog.getAllByRole("listitem").map((el) => el.textContent ?? "");
    expect(items[0]).toBe("Активные сотрудники: 2");
    expect(items[1]).toBe("Сотрудники: 5");
    expect(items).toContain("Наследуемые сопоставления должностей: 1");
    expect(items.join(" ")).not.toMatch(/legacy|active employees/i);
  });

  it("shows structured bulk delete results with localized dependencies", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-filter-status"));
    fireEvent.change(screen.getByTestId("org-units-filter-status"), { target: { value: "all" } });
    await waitFor(() => screen.getByTestId("org-unit-select-101"));
    fireEvent.click(screen.getByTestId("org-unit-select-101"));
    fireEvent.click(screen.getByTestId("org-unit-select-202"));
    fireEvent.click(screen.getByTestId("org-units-bulk-delete-btn"));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByText("Удалить выбранные"));

    await waitFor(() => expect(screen.getByTestId("org-units-bulk-results")).toBeInTheDocument());
    const panel = within(screen.getByTestId("org-units-bulk-results"));
    expect(panel.getByTestId("bulk-result-deleted-101")).toBeInTheDocument();
    expect(panel.getByTestId("bulk-result-failed-202")).toBeInTheDocument();
    expect(panel.getByText(/Пользователи: 1/)).toBeInTheDocument();
    expect(panel.getByText(/Уникальные должности: 1/)).toBeInTheDocument();
    expect(panel.getByText(/Наследуемые сопоставления должностей: 1/)).toBeInTheDocument();
    expect(panel.getByText(/Назначения: 1/)).toBeInTheDocument();
  });

  it("reloads list after closing bulk results", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-filter-status"));
    fireEvent.change(screen.getByTestId("org-units-filter-status"), { target: { value: "all" } });
    await waitFor(() => screen.getByTestId("org-unit-select-101"));
    fireEvent.click(screen.getByTestId("org-unit-select-101"));
    fireEvent.click(screen.getByTestId("org-units-bulk-delete-btn"));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByText("Удалить выбранные"));
    await waitFor(() => screen.getByTestId("org-units-bulk-results-close"));

    const callsBeforeClose = mockedList.mock.calls.length;
    fireEvent.click(screen.getByTestId("org-units-bulk-results-close"));
    await waitFor(() => expect(mockedList.mock.calls.length).toBeGreaterThan(callsBeforeClose));
  });

  it("shows activate action for inactive rows when inactive filter selected", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-filter-status"));
    fireEvent.change(screen.getByTestId("org-units-filter-status"), { target: { value: "inactive" } });
    await waitFor(() => screen.getByTestId("org-unit-toggle-active-202"));
    expect(screen.getByTestId("org-unit-toggle-active-202")).toHaveTextContent("Активировать");
  });

  it("renders visually separated action buttons", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-unit-actions-101"));
    const actions = screen.getByTestId("org-unit-actions-101");
    expect(within(actions).getByTestId("org-unit-view-101")).toHaveClass("rounded-md");
    expect(within(actions).getByTestId("org-unit-delete-101")).toHaveClass("text-red-700");
  });

  it("deletes safe unit after confirmation", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-unit-delete-101"));
    fireEvent.click(screen.getByTestId("org-unit-delete-101"));
    await waitFor(() => screen.getByText("Подтвердите удаление"));
    fireEvent.click(within(screen.getByRole("dialog")).getByText("Удалить"));
    await waitFor(() => expect(mockedDelete).toHaveBeenCalledWith(101));
  });

  it("reloads list after mutation", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-unit-delete-101"));
    const initialCalls = mockedList.mock.calls.length;
    fireEvent.click(screen.getByTestId("org-unit-delete-101"));
    await waitFor(() => screen.getByText("Подтвердите удаление"));
    fireEvent.click(within(screen.getByRole("dialog")).getByText("Удалить"));
    await waitFor(() => expect(mockedList.mock.calls.length).toBeGreaterThan(initialCalls));
  });
});
