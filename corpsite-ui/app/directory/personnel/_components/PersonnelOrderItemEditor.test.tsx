import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelOrderItemEditor from "./PersonnelOrderItemEditor";
import { createPersonnelOrderItem } from "../_lib/personnelOrdersApi.client";
import { loadScopedPositionOptions } from "@/lib/taskOrgFilters";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/directory/personnel/orders",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/app/directory/employees/_lib/api.client", () => ({
  getEmployees: vi.fn(async () => ({ items: [] })),
}));

vi.mock("@/lib/taskOrgFilters", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/taskOrgFilters")>();
  return {
    ...actual,
    loadScopedPositionOptions: vi.fn(async () => [{ id: 77, label: "Врач" }]),
  };
});

vi.mock("@/components/OrgScopeFilter", () => ({
  default: ({
    value,
    onChange,
  }: {
    value?: number | null;
    onChange?: (groupId: number | null) => void;
  }) => (
    <div>
      <label htmlFor="mock-org-group">Группа отделений</label>
      <select
        id="mock-org-group"
        data-testid="mock-org-group"
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
  }: {
    value?: number | null;
    onChange?: (unitId: number | null) => void;
    orgGroupId?: number | null;
  }) => (
    <div>
      <label htmlFor="mock-org-unit">Подразделение</label>
      <select
        id="mock-org-unit"
        data-testid="mock-org-unit"
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

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  vi.mocked(loadScopedPositionOptions).mockResolvedValue([{ id: 77, label: "Врач" }]);
  vi.mocked(createPersonnelOrderItem).mockResolvedValue({
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

describe("PersonnelOrderItemEditor org scope cascade", () => {
  it("renders group before unit/position and loads positions only for selected unit", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);

    expect(screen.getByTestId("personnel-order-org-scope-cascade")).toBeInTheDocument();
    expect(screen.getByLabelText("Группа отделений")).toBeInTheDocument();
    expect(screen.getByLabelText("Подразделение")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-position-select")).toBeDisabled();
    expect(loadScopedPositionOptions).not.toHaveBeenCalled();

    fireEvent.change(screen.getByTestId("mock-org-unit"), { target: { value: "10" } });

    await waitFor(() => {
      expect(loadScopedPositionOptions).toHaveBeenCalledWith({
        org_group_id: undefined,
        org_unit_id: 10,
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-position-select")).not.toBeDisabled();
    });
    expect(screen.getByRole("option", { name: "Врач" })).toBeInTheDocument();
  });

  it("clears unit and position when group changes", async () => {
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={vi.fn()} />);

    fireEvent.change(screen.getByTestId("mock-org-unit"), { target: { value: "10" } });
    await waitFor(() => {
      expect(screen.getByRole("option", { name: "Врач" })).toBeInTheDocument();
    });
    fireEvent.change(screen.getByTestId("personnel-order-position-select"), {
      target: { value: "77" },
    });
    expect(screen.getByTestId("personnel-order-position-select")).toHaveValue("77");

    fireEvent.change(screen.getByTestId("mock-org-group"), { target: { value: "2" } });

    expect(screen.getByTestId("mock-org-unit")).toHaveValue("");
    expect(screen.getByTestId("personnel-order-position-select")).toHaveValue("");
    expect(screen.getByTestId("personnel-order-position-select")).toBeDisabled();
  });

  it("clears position when unit changes and keeps payload without group id", async () => {
    const onChanged = vi.fn();
    render(<PersonnelOrderItemEditor orderId={1} items={[]} onChanged={onChanged} />);

    fireEvent.change(screen.getByTestId("mock-org-group"), { target: { value: "1" } });
    fireEvent.change(screen.getByTestId("mock-org-unit"), { target: { value: "10" } });
    await waitFor(() => {
      expect(loadScopedPositionOptions).toHaveBeenCalledWith({
        org_group_id: 1,
        org_unit_id: 10,
      });
    });
    fireEvent.change(screen.getByTestId("personnel-order-position-select"), {
      target: { value: "77" },
    });

    fireEvent.change(screen.getByTestId("mock-org-unit"), { target: { value: "11" } });
    expect(screen.getByTestId("personnel-order-position-select")).toHaveValue("");

    await waitFor(() => {
      expect(loadScopedPositionOptions).toHaveBeenCalledWith({
        org_group_id: 1,
        org_unit_id: 11,
      });
    });

    fireEvent.change(screen.getByTestId("personnel-order-position-select"), {
      target: { value: "77" },
    });
    fireEvent.change(screen.getByPlaceholderText("employee_id"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить пункт" }));

    await waitFor(() => {
      expect(createPersonnelOrderItem).toHaveBeenCalled();
    });

    const body = vi.mocked(createPersonnelOrderItem).mock.calls[0]?.[1] as {
      payload: Record<string, unknown>;
    };
    expect(body.payload).toEqual({
      org_unit_id: 11,
      position_id: 77,
      employment_rate: 1,
    });
    expect(body.payload).not.toHaveProperty("org_group_id");
    expect(body.payload).not.toHaveProperty("department_group_id");
  });
});
