import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getEmployee, getEmployees } from "@/app/directory/employees/_lib/api.client";
import PersonnelOrderItemEditor from "./PersonnelOrderItemEditor";
import { createPersonnelOrderItem, updatePersonnelOrderItem } from "../_lib/personnelOrdersApi.client";
import { loadScopedPositionOptions, loadGlobalPositionCatalogCached, resetGlobalPositionCatalogCache } from "@/lib/taskOrgFilters";
import { resolveEmployeeOrgScopePrefill } from "@/lib/userCreateOrgScope";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/directory/personnel/orders",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/lib/userCreateOrgScope", () => ({
  resolveEmployeeOrgScopePrefill: vi.fn(async (unitId: number) => ({
    org_group_id: unitId === 73 ? 2 : 1,
    org_unit_id: unitId,
  })),
}));

vi.mock("@/lib/orgScope", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/orgScope")>();
  return {
    ...actual,
    fetchDepartmentGroups: vi.fn(async () => [
      { group_id: 1, group_name: "Группа 1" },
      { group_id: 2, group_name: "Группа 2" },
    ]),
  };
});

vi.mock("@/app/directory/employees/_lib/api.client", () => ({
  getEmployees: vi.fn(async () => ({ items: [], total: 0 })),
  getEmployee: vi.fn(),
}));

vi.mock("@/lib/taskOrgFilters", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/taskOrgFilters")>();
  return {
    ...actual,
    loadScopedPositionOptions: vi.fn(async () => [
      { id: 77, label: "Врач" },
      { id: 78, label: "Заведующий" },
    ]),
    loadGlobalPositionCatalogCached: vi.fn(async () => [
      { id: 77, label: "Врач" },
      { id: 78, label: "Заведующий" },
      { id: 88, label: "Медсестра" },
      { id: 89, label: "Кадровый специалист" },
      { id: 90, label: "Врач" },
    ]),
  };
});

vi.mock("@/components/OrgScopeFilter", () => ({
  default: ({
    value,
    onChange,
    label,
  }: {
    value?: number | null;
    onChange?: (groupId: number | null) => void;
    label?: string;
  }) => (
    <div>
      <label htmlFor={`mock-org-group-${label}`}>{label}</label>
      <select
        id={`mock-org-group-${label}`}
        data-testid={`mock-org-group-${label}`}
        value={value != null ? String(value) : ""}
        onChange={(e) => onChange?.(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">Все</option>
        <option value="1">Группа 1</option>
        <option value="2">Группа 2</option>
      </select>
    </div>
  ),
}));

vi.mock("@/components/OrgUnitScopeFilter", () => ({
  default: ({
    value,
    onChange,
    orgGroupId,
    label,
  }: {
    value?: number | null;
    onChange?: (unitId: number | null) => void;
    orgGroupId?: number | null;
    label?: string;
  }) => (
    <div>
      <label htmlFor={`mock-org-unit-${label}`}>{label}</label>
      <select
        id={`mock-org-unit-${label}`}
        data-testid={`mock-org-unit-${label}`}
        value={value != null ? String(value) : ""}
        onChange={(e) => onChange?.(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">Выберите подразделение</option>
        {orgGroupId === 2 ? (
          <option value="20">Отделение B</option>
        ) : (
          <>
            <option value="10">Отделение A</option>
            <option value="11">Отделение C</option>
          </>
        )}
      </select>
    </div>
  ),
}));

vi.mock("../_lib/personnelOrdersApi.client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../_lib/personnelOrdersApi.client")>();
  return {
    ...actual,
    createPersonnelOrderItem: vi.fn(),
    updatePersonnelOrderItem: vi.fn(),
  };
});

const activeEmployee = {
  id: "138",
  fio: "Макибаева Акмарал Сабитовна",
  department: null,
  position: { id: 86, name: "Руководитель отдела кадров" },
  org_unit: {
    unit_id: 73,
    name: "Отдел кадров",
    code: null,
    parent_unit_id: null,
    is_active: true,
  },
  rate: "1",
  status: "active",
  date_from: null,
  date_to: null,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  resetGlobalPositionCatalogCache();
  vi.mocked(getEmployees).mockResolvedValue({ items: [], total: 0 });
  vi.mocked(getEmployee).mockResolvedValue(activeEmployee);
  vi.mocked(loadScopedPositionOptions).mockResolvedValue([
    { id: 77, label: "Врач" },
    { id: 78, label: "Заведующий" },
  ]);
  vi.mocked(loadGlobalPositionCatalogCached).mockResolvedValue([
    { id: 77, label: "Врач" },
    { id: 78, label: "Заведующий" },
    { id: 88, label: "Медсестра" },
    { id: 89, label: "Кадровый специалист" },
    { id: 90, label: "Врач" },
  ]);
  vi.mocked(createPersonnelOrderItem).mockResolvedValue({
    order: {
      order_id: 1,
      order_type_code: "TRANSFER",
      order_class: "SIMPLE",
      status: "DRAFT",
      source_mode: "PAPER",
      created_by: 1,
    },
    items: [],
    localized_texts: [],
    attachments: [],
    prints: [],
    events: [],
  });
  vi.mocked(updatePersonnelOrderItem).mockResolvedValue({
    order: {
      order_id: 1,
      order_type_code: "HIRE",
      order_class: "SIMPLE",
      status: "DRAFT",
      source_mode: "PAPER",
      created_by: 1,
    },
    items: [],
    localized_texts: [],
    attachments: [],
    prints: [],
    events: [],
  });
});

async function selectEmployeeFromSearch() {
  vi.mocked(getEmployees).mockResolvedValue({
    items: [activeEmployee],
    total: 1,
  });
  fireEvent.change(screen.getByTestId("personnel-order-employee-search-input"), {
    target: { value: "Маки" },
  });
  fireEvent.click(await screen.findByTestId("personnel-order-employee-option-138"));
  await waitFor(() => {
    expect(screen.getByTestId("personnel-order-current-placement")).toBeInTheDocument();
  });
}

describe("PersonnelOrderItemEditor employee autocomplete", () => {
  it("shows matching active employees after typing a surname", async () => {
    vi.mocked(getEmployees).mockResolvedValue({
      items: [activeEmployee],
      total: 1,
    });

    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);

    fireEvent.change(screen.getByTestId("personnel-order-employee-search-input"), {
      target: { value: "Маки" },
    });

    await waitFor(
      () => {
        expect(getEmployees).toHaveBeenCalledWith({
          q: "Маки",
          limit: 20,
          status: "active",
        });
      },
      { timeout: 2000 },
    );

    expect(await screen.findByTestId("personnel-order-employee-option-138")).toBeInTheDocument();
  });

  it("stores employee_id and shows current placement after selecting an option", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);

    await selectEmployeeFromSearch();

    expect(screen.getByTestId("personnel-order-employee-id-input")).toHaveValue("138");
    expect(screen.getByTestId("personnel-order-employee-search-input")).toHaveValue(
      "Макибаева Акмарал Сабитовна",
    );
    expect(screen.queryByTestId("personnel-order-employee-search-results")).not.toBeInTheDocument();
    expect(await screen.findByTestId("personnel-order-current-placement")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-current-org-unit")).toHaveTextContent("Отдел кадров");
    expect(screen.getByTestId("personnel-order-current-position")).toHaveTextContent(
      "Руководитель отдела кадров",
    );
    expect(screen.getByTestId("personnel-order-current-rate")).toHaveTextContent("1");
  });
});

describe("PersonnelOrderItemEditor TRANSFER", () => {
  it("shows source read-only and separate target placement cascade", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);
    await selectEmployeeFromSearch();

    expect(screen.getByTestId("personnel-order-current-placement")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-target-placement")).toBeInTheDocument();
    expect(screen.getByText("Новое назначение")).toBeInTheDocument();
    expect(screen.getByLabelText("Подразделение")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-position-select")).toBeInTheDocument();
  });

  it("clears target fields when employee changes", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);
    await selectEmployeeFromSearch();

    fireEvent.change(screen.getByTestId("mock-org-unit-Подразделение"), {
      target: { value: "10" },
    });
    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-position-select")).not.toBeDisabled();
    });
    fireEvent.change(screen.getByTestId("personnel-order-position-select"), {
      target: { value: "77" },
    });
    fireEvent.change(screen.getByTestId("personnel-order-target-rate-input"), {
      target: { value: "0.5" },
    });

    vi.mocked(getEmployees).mockResolvedValue({
      items: [
        {
          ...activeEmployee,
          id: "200",
          fio: "Другой Сотрудник",
          org_unit: { ...activeEmployee.org_unit, unit_id: 20, name: "Отделение B" },
        },
      ],
      total: 1,
    });
    fireEvent.change(screen.getByTestId("personnel-order-employee-search-input"), {
      target: { value: "Друг" },
    });
    fireEvent.click(await screen.findByTestId("personnel-order-employee-option-200"));

    await waitFor(() => {
      expect(screen.getByTestId("mock-org-unit-Подразделение")).toHaveValue("");
      expect(screen.getByTestId("personnel-order-position-select")).toHaveValue("");
      expect(screen.getByTestId("personnel-order-target-rate-input")).toHaveValue("");
      expect(screen.getByTestId("personnel-order-current-org-unit")).toHaveTextContent("Отделение B");
    });
  });

  it("loads positions for selected target unit with org_group_id", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);

    fireEvent.change(screen.getByTestId("mock-org-group-Группа отделений"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByTestId("mock-org-unit-Подразделение"), {
      target: { value: "10" },
    });

    await waitFor(() => {
      expect(loadScopedPositionOptions).toHaveBeenCalledWith({
        org_group_id: 1,
        org_unit_id: 10,
        scope: "allowed",
      });
    });
  });

  it("clears unit and position when department group changes", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);

    fireEvent.change(screen.getByTestId("mock-org-group-Группа отделений"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByTestId("mock-org-unit-Подразделение"), {
      target: { value: "10" },
    });
    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-position-select")).not.toBeDisabled();
    });
    fireEvent.change(screen.getByTestId("personnel-order-position-select"), {
      target: { value: "77" },
    });

    fireEvent.change(screen.getByTestId("mock-org-group-Группа отделений"), {
      target: { value: "2" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("mock-org-unit-Подразделение")).toHaveValue("");
      expect(screen.getByTestId("personnel-order-position-select")).toHaveValue("");
    });
  });

  it("clears position when org unit changes", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);

    fireEvent.change(screen.getByTestId("mock-org-group-Группа отделений"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByTestId("mock-org-unit-Подразделение"), {
      target: { value: "10" },
    });
    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-position-select")).not.toBeDisabled();
    });
    fireEvent.change(screen.getByTestId("personnel-order-position-select"), {
      target: { value: "77" },
    });

    fireEvent.change(screen.getByTestId("mock-org-unit-Подразделение"), {
      target: { value: "11" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-position-select")).toHaveValue("");
      expect(loadScopedPositionOptions).toHaveBeenLastCalledWith({
        org_group_id: 1,
        org_unit_id: 11,
        scope: "allowed",
      });
    });
  });

  it("keeps global position selectable when it is absent from scoped list", async () => {
    vi.mocked(loadScopedPositionOptions).mockResolvedValueOnce([{ id: 78, label: "Заведующий" }]);
    vi.mocked(loadGlobalPositionCatalogCached).mockResolvedValue([
      { id: 77, label: "Врач" },
      { id: 78, label: "Заведующий" },
      { id: 89, label: "Кадровый специалист" },
    ]);

    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);

    fireEvent.change(screen.getByTestId("mock-org-group-Группа отделений"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByTestId("mock-org-unit-Подразделение"), {
      target: { value: "10" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-position-select")).not.toBeDisabled();
    });

    fireEvent.change(screen.getByTestId("personnel-order-position-select"), {
      target: { value: "89" },
    });

    expect(screen.getByTestId("personnel-order-position-select")).toHaveValue("89");
  });
});

describe("PersonnelOrderItemEditor position catalog", () => {
  it("shows scoped and global positions with optgroups", async () => {
    render(<PersonnelOrderItemEditor orderId={1} orderTypeCode="HIRE" items={[]} onChanged={vi.fn()} />);

    fireEvent.change(screen.getByTestId("mock-org-group-Группа отделений"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByTestId("mock-org-unit-Подразделение"), {
      target: { value: "10" },
    });

    await waitFor(() => {
      expect(loadScopedPositionOptions).toHaveBeenCalledWith({
        org_group_id: 1,
        org_unit_id: 10,
        scope: "allowed",
      });
      expect(loadGlobalPositionCatalogCached).toHaveBeenCalledTimes(1);
    });

    const positionSelect = screen.getByTestId("personnel-order-position-select") as HTMLSelectElement;
    await waitFor(() => {
      expect(positionSelect).not.toBeDisabled();
    });

    const optgroups = Array.from(positionSelect.querySelectorAll("optgroup"));
    expect(optgroups.map((node) => node.getAttribute("label"))).toEqual([
      "Разрешённые для подразделения",
      "Все должности",
    ]);
    expect(positionSelect.querySelectorAll("option").length).toBeGreaterThanOrEqual(5);
    expect(screen.getByRole("option", { name: "Кадровый специалист" })).toBeInTheDocument();
    expect(screen.getAllByRole("option", { name: "Врач" }).length).toBeGreaterThanOrEqual(1);
  });

  it("allows selecting a global position not used in the selected unit", async () => {
    render(<PersonnelOrderItemEditor orderId={1} orderTypeCode="HIRE" items={[]} onChanged={vi.fn()} />);

    fireEvent.change(screen.getByTestId("mock-org-group-Группа отделений"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByTestId("mock-org-unit-Подразделение"), {
      target: { value: "10" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-position-select")).not.toBeDisabled();
    });

    fireEvent.change(screen.getByTestId("personnel-order-position-select"), {
      target: { value: "89" },
    });

    expect(screen.getByTestId("personnel-order-position-select")).toHaveValue("89");
  });

  it("does not reload global catalog when org unit changes", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);

    fireEvent.change(screen.getByTestId("mock-org-group-Группа отделений"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByTestId("mock-org-unit-Подразделение"), {
      target: { value: "10" },
    });

    await waitFor(() => {
      expect(loadGlobalPositionCatalogCached).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByTestId("mock-org-unit-Подразделение"), {
      target: { value: "11" },
    });

    await waitFor(() => {
      expect(loadScopedPositionOptions).toHaveBeenLastCalledWith({
        org_group_id: 1,
        org_unit_id: 11,
        scope: "allowed",
      });
    });
    expect(loadGlobalPositionCatalogCached).toHaveBeenCalledTimes(1);
  });
});

describe("PersonnelOrderItemEditor TERMINATION", () => {
  it("shows current placement and termination reason without target cascade", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);

    fireEvent.change(screen.getByTestId("personnel-order-item-type-select"), {
      target: { value: "TERMINATION" },
    });
    await selectEmployeeFromSearch();

    expect(screen.getByTestId("personnel-order-current-placement")).toBeInTheDocument();
    expect(screen.queryByTestId("personnel-order-target-placement")).not.toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-termination-reason-input")).toBeInTheDocument();
    expect(screen.queryByTestId("personnel-order-target-rate-input")).not.toBeInTheDocument();
    expect(screen.getByText("Дата увольнения")).toBeInTheDocument();
  });
});

describe("PersonnelOrderItemEditor RATE_CHANGE", () => {
  it("shows current rate and editable new rate without target org fields", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);

    fireEvent.change(screen.getByTestId("personnel-order-item-type-select"), {
      target: { value: "RATE_CHANGE" },
    });
    await selectEmployeeFromSearch();

    expect(screen.getByTestId("personnel-order-current-placement")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-current-rate")).toHaveTextContent("1");
    expect(screen.getByTestId("personnel-order-new-rate-input")).toBeInTheDocument();
    expect(screen.queryByTestId("personnel-order-target-placement")).not.toBeInTheDocument();
  });

  it("persists as TRANSFER with to_rate only", async () => {
    const onChanged = vi.fn();
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={onChanged} />);

    fireEvent.change(screen.getByTestId("personnel-order-item-type-select"), {
      target: { value: "RATE_CHANGE" },
    });
    await selectEmployeeFromSearch();
    fireEvent.change(screen.getByTestId("personnel-order-new-rate-input"), {
      target: { value: "0.75" },
    });
    fireEvent.change(screen.getByTestId("personnel-order-employee-id-input"), {
      target: { value: "138" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Добавить пункт" }));

    await waitFor(() => {
      expect(createPersonnelOrderItem).toHaveBeenCalled();
    });

    const body = vi.mocked(createPersonnelOrderItem).mock.calls[0]?.[1] as {
      item_type_code: string;
      employee_id: number;
      payload: Record<string, unknown>;
    };
    expect(body.item_type_code).toBe("TRANSFER");
    expect(body.employee_id).toBe(138);
    expect(body.payload).toEqual({ to_rate: 0.75 });
  });
});

describe("PersonnelOrderItemEditor HIRE", () => {
  it("renders hire placement with new-employee option when HIRE is selected", async () => {
    render(<PersonnelOrderItemEditor orderId={1} orderTypeCode="HIRE" items={[]} onChanged={vi.fn()} />);

    expect(screen.getByTestId("personnel-order-item-type-select")).toHaveValue("HIRE");
    expect(screen.getByTestId("personnel-order-hire-legacy")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-pending-new-employee")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-pending-new-employee")).toBeEnabled();
    expect(screen.queryByTestId("personnel-order-current-placement")).not.toBeInTheDocument();
  });

  it("allows saving hire item without employee when pending new employee is checked", async () => {
    const onChanged = vi.fn();
    render(<PersonnelOrderItemEditor orderId={1} orderTypeCode="HIRE" items={[]} onChanged={onChanged} />);

    fireEvent.click(screen.getByTestId("personnel-order-pending-new-employee"));
    fireEvent.click(screen.getByRole("button", { name: "Добавить пункт" }));

    await waitFor(() => {
      expect(createPersonnelOrderItem).toHaveBeenCalled();
    });

    const body = vi.mocked(createPersonnelOrderItem).mock.calls[0]?.[1] as {
      item_type_code: string;
      employee_id: number | null;
    };
    expect(body.item_type_code).toBe("HIRE");
    expect(body.employee_id).toBeNull();
  });

  it("uses status=all for HIRE employee search", async () => {
    render(<PersonnelOrderItemEditor orderId={1} orderTypeCode="HIRE" items={[]} onChanged={vi.fn()} />);

    fireEvent.change(screen.getByTestId("personnel-order-employee-search-input"), {
      target: { value: "Ива" },
    });

    await waitFor(
      () => {
        expect(getEmployees).toHaveBeenCalledWith({
          q: "Ива",
          limit: 20,
          status: "all",
        });
      },
      { timeout: 2000 },
    );
  });

  it("disables pending-new-employee checkbox when editing saved HIRE with employee_id", async () => {
    render(
      <PersonnelOrderItemEditor
        orderId={1}
        orderTypeCode="HIRE"
        items={[
          {
            item_id: 21,
            item_number: 1,
            item_type_code: "HIRE",
            item_status: "ACTIVE",
            employee_id: 138,
            employee_name: "Макибаева Акмарал Сабитовна",
            effective_date: "2026-03-01",
            payload: { org_unit_id: 10, position_id: 77, employment_rate: 1 },
          },
        ]}
        onChanged={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Изменить" }));

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-pending-new-employee")).toBeDisabled();
    });
    expect(screen.getByTestId("personnel-order-pending-new-employee-reset-blocked")).toHaveTextContent(
      "Сброс сотрудника в сохранённом пункте пока не поддерживается.",
    );
    expect(screen.getByTestId("personnel-order-pending-new-employee")).not.toBeChecked();
    expect(screen.getByTestId("personnel-order-employee-id-input")).toHaveValue("138");

    fireEvent.click(screen.getByTestId("personnel-order-pending-new-employee"));
    fireEvent.change(screen.getByTestId("personnel-order-employee-id-input"), { target: { value: "" } });
    fireEvent.change(screen.getByTestId("personnel-order-employee-search-input"), {
      target: { value: "" },
    });

    expect(screen.getByTestId("personnel-order-pending-new-employee")).toBeDisabled();
    expect(screen.getByTestId("personnel-order-pending-new-employee")).not.toBeChecked();
  });

  it("allows assigning employee when editing saved HIRE without employee_id", async () => {
    const onChanged = vi.fn();
    render(
      <PersonnelOrderItemEditor
        orderId={1}
        orderTypeCode="HIRE"
        items={[
          {
            item_id: 22,
            item_number: 1,
            item_type_code: "HIRE",
            item_status: "ACTIVE",
            employee_id: null,
            employee_name: null,
            effective_date: "2026-03-01",
            payload: { org_unit_id: 10, position_id: 77, employment_rate: 1 },
          },
        ]}
        onChanged={onChanged}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Изменить" }));

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-pending-new-employee")).toBeEnabled();
      expect(screen.getByTestId("personnel-order-pending-new-employee")).toBeChecked();
    });

    fireEvent.click(screen.getByTestId("personnel-order-pending-new-employee"));

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-pending-new-employee")).not.toBeChecked();
      expect(screen.getByTestId("personnel-order-employee-search-input")).toBeInTheDocument();
    });

    vi.mocked(getEmployees).mockResolvedValue({
      items: [activeEmployee],
      total: 1,
    });
    fireEvent.change(screen.getByTestId("personnel-order-employee-search-input"), {
      target: { value: "Маки" },
    });
    fireEvent.click(await screen.findByTestId("personnel-order-employee-option-138"));

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-pending-new-employee")).not.toBeChecked();
      expect(screen.getByTestId("personnel-order-employee-id-input")).toHaveValue("138");
    });

    fireEvent.click(screen.getByRole("button", { name: "Сохранить пункт" }));

    await waitFor(() => {
      expect(updatePersonnelOrderItem).toHaveBeenCalledWith(1, 22, expect.any(Object));
    });

    const body = vi.mocked(updatePersonnelOrderItem).mock.calls[0]?.[2] as {
      employee_id: number | null;
    };
    expect(body.employee_id).toBe(138);
  });

  it("keeps pending-new-employee disabled when item type changes to HIRE on saved employee", async () => {
    render(
      <PersonnelOrderItemEditor
        orderId={1}
        orderTypeCode="COMPOSITE"
        items={[
          {
            item_id: 23,
            item_number: 1,
            item_type_code: "TRANSFER",
            item_status: "ACTIVE",
            employee_id: 138,
            employee_name: "Макибаева Акмарал Сабитовна",
            effective_date: "2026-01-01",
            payload: { to_org_unit_id: 73, to_position_id: 86, to_rate: 1 },
          },
        ]}
        onChanged={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Изменить" }));
    fireEvent.change(screen.getByTestId("personnel-order-item-type-select"), {
      target: { value: "HIRE" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-pending-new-employee")).toBeDisabled();
    });
    expect(screen.getByTestId("personnel-order-pending-new-employee-reset-blocked")).toBeInTheDocument();
  });
});

describe("PersonnelOrderItemEditor non-HIRE pending guard", () => {
  it("does not show pending-new-employee checkbox for TRANSFER", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);
    expect(screen.queryByTestId("personnel-order-pending-new-employee")).not.toBeInTheDocument();
  });

  it("does not show pending-new-employee checkbox for TERMINATION", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);
    fireEvent.change(screen.getByTestId("personnel-order-item-type-select"), {
      target: { value: "TERMINATION" },
    });
    expect(screen.queryByTestId("personnel-order-pending-new-employee")).not.toBeInTheDocument();
  });

  it("does not show pending-new-employee checkbox for RATE_CHANGE", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);
    fireEvent.change(screen.getByTestId("personnel-order-item-type-select"), {
      target: { value: "RATE_CHANGE" },
    });
    expect(screen.queryByTestId("personnel-order-pending-new-employee")).not.toBeInTheDocument();
  });
});

describe("PersonnelOrderItemEditor startEdit org scope", () => {
  it("resolves target org group when editing a TRANSFER item", async () => {
    render(
      <PersonnelOrderItemEditor
        orderId={1}
        items={[
          {
            item_id: 9,
            item_number: 1,
            item_type_code: "TRANSFER",
            item_status: "ACTIVE",
            employee_id: 138,
            employee_name: "Макибаева Акмарал Сабитовна",
            effective_date: "2026-01-01",
            payload: { to_org_unit_id: 73, to_position_id: 86, to_rate: 1 },
          },
        ]}
        onChanged={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Изменить" }));

    await waitFor(() => {
      expect(resolveEmployeeOrgScopePrefill).toHaveBeenCalledWith(73);
    });
    await waitFor(() => {
      expect(screen.getByTestId("mock-org-group-Группа отделений")).toHaveValue("2");
    });
    expect(screen.getByTestId("personnel-order-item-type-select")).toHaveValue("TRANSFER");
  });

  it("opens RATE_CHANGE form for TRANSFER item with to_rate only", async () => {
    render(
      <PersonnelOrderItemEditor
        orderId={1}
        items={[
          {
            item_id: 10,
            item_number: 2,
            item_type_code: "TRANSFER",
            item_status: "ACTIVE",
            employee_id: 138,
            employee_name: "Макибаева Акмарал Сабитовна",
            effective_date: "2026-02-01",
            payload: { to_rate: 0.5 },
          },
        ]}
        onChanged={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Изменить" }));

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-item-type-select")).toHaveValue("RATE_CHANGE");
    });
    expect(screen.getByTestId("personnel-order-new-rate-input")).toHaveValue("0.5");
  });
});
