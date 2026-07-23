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
    previewBulkDeleteAdminOrgUnits: vi.fn(),
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
  previewBulkDeleteAdminOrgUnits,
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
const mockedBulkPreview = vi.mocked(previewBulkDeleteAdminOrgUnits);

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
    return { items, total: items.length, limit: 50, offset: params.offset ?? 0 };
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
    mockedBulkPreview.mockImplementation(async (ids) => ({
      requested: ids.length,
      roots: ids.map((id) => {
        const unit = sampleUnits.find((row) => row.unit_id === id);
        return {
          id,
          name: unit?.name ?? `ID ${id}`,
          descendants: [],
          subtree_size: 1,
        };
      }),
      skipped_as_covered: [],
      not_found: [],
    }));
    mockedBulkDelete.mockResolvedValue({
      deleted_ids: [101],
      failed: [
        {
          id: 202,
          name: "Отдел кадров",
          reason_code: "ORG_UNIT_HAS_DEPENDENCIES",
          message: "Подразделение используется в системе (4 связанных записей)",
          dependencies: {
            users: 1,
            org_unique_position: 1,
            legacy_position_mapping: 1,
            person_assignments: 1,
          },
        },
      ],
      requested: 2,
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

  it("shows empty parent option on create and enables group selection for root", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-create-btn"));
    fireEvent.click(screen.getByTestId("org-units-create-btn"));

    const parentSelect = screen.getByTestId("org-unit-form-parent") as HTMLSelectElement;
    const groupSelect = screen.getByTestId("org-unit-form-group") as HTMLSelectElement;
    expect(within(parentSelect).getByText("— выберите родителя —")).toBeInTheDocument();
    expect(parentSelect.value).toBe("");
    expect(groupSelect.disabled).toBe(false);
  });

  it("creates root org unit without parent", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-create-btn"));
    fireEvent.click(screen.getByTestId("org-units-create-btn"));

    fireEvent.change(screen.getByTestId("org-unit-form-name"), { target: { value: "Корневое подразделение" } });
    fireEvent.change(screen.getByTestId("org-unit-form-group"), { target: { value: "2" } });
    fireEvent.click(screen.getByTestId("org-unit-form-save"));

    await waitFor(() =>
      expect(mockedCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: "Корневое подразделение",
          parent_unit_id: null,
          group_id: 2,
        }),
      ),
    );
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

  it("creates child org unit with inherited parent group", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-create-btn"));
    fireEvent.click(screen.getByTestId("org-units-create-btn"));

    const parentSelect = screen.getByTestId("org-unit-form-parent") as HTMLSelectElement;
    const groupSelect = screen.getByTestId("org-unit-form-group") as HTMLSelectElement;
    fireEvent.change(parentSelect, { target: { value: "10" } });
    expect(groupSelect.disabled).toBe(true);
    expect(groupSelect.value).toBe("1");

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

  it("selects and deselects a single row", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-unit-select-101"));

    fireEvent.click(screen.getByTestId("org-unit-select-101"));
    expect(screen.getByTestId("org-units-selected-count")).toHaveTextContent("Выбрано: 1");
    expect(screen.getByTestId("org-units-bulk-delete-btn")).not.toBeDisabled();

    fireEvent.click(screen.getByTestId("org-unit-select-101"));
    expect(screen.getByTestId("org-units-selected-count")).toHaveTextContent("Выбрано: 0");
    expect(screen.getByTestId("org-units-bulk-delete-btn")).toBeDisabled();
  });

  it("selects all rows on the current page and clears page selection", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-select-all-page"));

    fireEvent.click(screen.getByTestId("org-units-select-all-page"));
    expect(screen.getByTestId("org-units-selected-count")).toHaveTextContent("Выбрано: 2");

    fireEvent.click(screen.getByTestId("org-units-select-all-page"));
    expect(screen.getByTestId("org-units-selected-count")).toHaveTextContent("Выбрано: 0");
  });

  it("shows bulk delete confirmation with selected units and irreversibility warning", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-unit-select-101"));
    fireEvent.click(screen.getByTestId("org-unit-select-101"));
    fireEvent.click(screen.getByTestId("org-units-bulk-delete-btn"));

    await waitFor(() => expect(mockedBulkPreview).toHaveBeenCalledWith([101]));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Действие необратимо/)).toBeInTheDocument();
    expect(within(dialog).getByTestId("org-units-bulk-confirm-list")).toHaveTextContent("Тестовое подразделение");
    expect(within(dialog).getByText("Удалить выбранные")).toBeInTheDocument();
  });

  it("shows descendant warning before bulk delete confirmation", async () => {
    mockedBulkPreview.mockResolvedValueOnce({
      requested: 1,
      roots: [
        {
          id: 202,
          name: "Отдел кадров",
          descendants: [
            { id: 301, name: "Группа кадров" },
            { id: 302, name: "Архив кадров" },
          ],
          subtree_size: 3,
        },
      ],
      skipped_as_covered: [],
      not_found: [],
    });

    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-filter-status"));
    fireEvent.change(screen.getByTestId("org-units-filter-status"), { target: { value: "inactive" } });
    await waitFor(() => screen.getByTestId("org-unit-select-202"));
    fireEvent.click(screen.getByTestId("org-unit-select-202"));
    fireEvent.click(screen.getByTestId("org-units-bulk-delete-btn"));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/2 дочерними/)).toBeInTheDocument();
    expect(within(dialog).getByTestId("org-units-bulk-confirm-descendants")).toHaveTextContent(
      "Группа кадров",
    );
    expect(within(dialog).getByText("Также будут удалены дочерние подразделения")).toBeInTheDocument();
  });

  it("cancels bulk delete confirmation without calling delete API", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-unit-select-101"));
    fireEvent.click(screen.getByTestId("org-unit-select-101"));
    fireEvent.click(screen.getByTestId("org-units-bulk-delete-btn"));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(mockedBulkPreview).toHaveBeenCalled());
    fireEvent.click(within(dialog).getByText("Отмена"));

    expect(mockedBulkDelete).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("shows covered-child note when parent and child are selected together", async () => {
    mockedBulkPreview.mockResolvedValueOnce({
      requested: 2,
      roots: [{ id: 202, name: "Отдел кадров", descendants: [{ id: 303, name: "Группа" }], subtree_size: 2 }],
      skipped_as_covered: [{ id: 303, covered_by: 202 }],
      not_found: [],
    });

    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-filter-status"));
    fireEvent.change(screen.getByTestId("org-units-filter-status"), { target: { value: "all" } });
    await waitFor(() => screen.getByTestId("org-unit-select-101"));
    fireEvent.click(screen.getByTestId("org-unit-select-101"));
    fireEvent.click(screen.getByTestId("org-unit-select-202"));
    fireEvent.click(screen.getByTestId("org-units-bulk-delete-btn"));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByTestId("org-units-bulk-confirm-covered-note")).toBeInTheDocument();
  });

  it("handles partial bulk delete success and keeps failed selection", async () => {
    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-units-filter-status"));
    fireEvent.change(screen.getByTestId("org-units-filter-status"), { target: { value: "all" } });
    await waitFor(() => screen.getByTestId("org-unit-select-101"));
    fireEvent.click(screen.getByTestId("org-unit-select-101"));
    fireEvent.click(screen.getByTestId("org-unit-select-202"));
    fireEvent.click(screen.getByTestId("org-units-bulk-delete-btn"));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(mockedBulkPreview).toHaveBeenCalled());
    fireEvent.click(within(dialog).getByText("Удалить выбранные"));

    await waitFor(() => expect(mockedBulkDelete).toHaveBeenCalledWith([101, 202]));
    await waitFor(() => expect(screen.getByTestId("org-units-bulk-results")).toBeInTheDocument());
    expect(screen.getByText(/Удалено 1 из 2/)).toBeInTheDocument();
    expect(screen.getByText(/Пропущено:/)).toBeInTheDocument();
    expect(screen.getByTestId("org-units-selected-count")).toHaveTextContent("Выбрано: 1");
    expect(screen.getByTestId("org-unit-select-202")).toBeChecked();
    expect(screen.getByTestId("org-unit-select-101")).not.toBeChecked();
  });

  it("handles full bulk delete failure", async () => {
    mockedBulkDelete.mockResolvedValueOnce({
      deleted_ids: [],
      failed: [
        {
          id: 101,
          name: "Тестовое подразделение",
          reason_code: "SUBTREE_HAS_DEPENDENCIES",
          message: "Удаление поддерева заблокировано: есть внешние зависимости",
          blocked_units: [{ id: 101, name: "Тестовое подразделение", dependencies: { users: 2 } }],
        },
      ],
      requested: 1,
    });

    render(<OrgUnitsAdminClient />);
    await waitFor(() => screen.getByTestId("org-unit-select-101"));
    fireEvent.click(screen.getByTestId("org-unit-select-101"));
    fireEvent.click(screen.getByTestId("org-units-bulk-delete-btn"));
    const dialog = await screen.findByRole("dialog");
    await waitFor(() => expect(mockedBulkPreview).toHaveBeenCalled());
    fireEvent.click(within(dialog).getByText("Удалить выбранные"));

    await waitFor(() => expect(screen.getByTestId("org-units-bulk-results")).toBeInTheDocument());
    expect(screen.getByText(/Удалено 0 из 1/)).toBeInTheDocument();
    expect(screen.queryByTestId("bulk-result-deleted-101")).not.toBeInTheDocument();
    expect(screen.getByTestId("bulk-result-failed-101")).toBeInTheDocument();
    expect(screen.getByText(/Пользователи: 2/)).toBeInTheDocument();
    expect(screen.getByTestId("org-units-selected-count")).toHaveTextContent("Выбрано: 1");
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
    await waitFor(() => expect(mockedBulkPreview).toHaveBeenCalled());
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
    await waitFor(() => expect(mockedBulkPreview).toHaveBeenCalled());
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
