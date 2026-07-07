// FILE: corpsite-ui/lib/regularTaskTemplateFiltersBar.test.tsx
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import RegularTaskTemplateFiltersBar from "@/components/RegularTaskTemplateFiltersBar";

const onChange = vi.fn();

vi.mock("@/lib/orgScope", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/orgScope")>();
  return {
    ...actual,
    fetchDepartmentGroups: vi.fn(async () => [
      { group_id: 1, group_name: "Амбулаторная" },
      { group_id: 3, group_name: "Административная" },
    ]),
  };
});

vi.mock("@/lib/orgUnitsSelect", () => ({
  loadOrgUnitSelectOptions: vi.fn(async () => [
    { unit_id: 44, name: "ОВЭиПД", group_id: 1 },
    { unit_id: 73, name: "Отдел кадров", group_id: 3 },
  ]),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("RegularTaskTemplateFiltersBar", () => {
  it("renders linked filters without reset when nothing is selected", async () => {
    render(
      <RegularTaskTemplateFiltersBar
        filters={{}}
        onChange={onChange}
        executorRoleOptions={[{ role_id: 14, name: "HR_HEAD", code: "HR_HEAD" }]}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("regular-task-template-filter-group")).toBeInTheDocument();
    });

    expect(screen.getByTestId("regular-task-template-filter-unit")).toBeInTheDocument();
    expect(screen.getByTestId("regular-task-template-filter-role")).toBeInTheDocument();
    expect(screen.queryByTestId("regular-task-template-filter-reset")).not.toBeInTheDocument();
  });

  it("shows reset and clears filters", async () => {
    render(
      <RegularTaskTemplateFiltersBar
        filters={{ org_group_id: 3, org_unit_id: 73, executor_role_id: 14 }}
        onChange={onChange}
        executorRoleOptions={[{ role_id: 14, name: "HR_HEAD", code: "HR_HEAD" }]}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("regular-task-template-filter-reset")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("regular-task-template-filter-reset"));
    expect(onChange).toHaveBeenCalledWith({});
  });

  it("limits departments by selected group and clears unit on group reset", async () => {
    render(
      <RegularTaskTemplateFiltersBar
        filters={{ org_group_id: 3, org_unit_id: 73 }}
        onChange={onChange}
        executorRoleOptions={[]}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("regular-task-template-filter-unit")).toBeInTheDocument();
    });

    const unitSelect = screen.getByTestId("regular-task-template-filter-unit") as HTMLSelectElement;
    const unitOptions = Array.from(unitSelect.options).map((opt) => opt.text);
    expect(unitOptions).toContain("Отдел кадров");
    expect(unitOptions).not.toContain("ОВЭиПД");

    fireEvent.change(screen.getByTestId("regular-task-template-filter-group"), {
      target: { value: "" },
    });

    expect(onChange).toHaveBeenCalledWith({});
  });

  it("passes executor role filter changes", async () => {
    render(
      <RegularTaskTemplateFiltersBar
        filters={{}}
        onChange={onChange}
        executorRoleOptions={[{ role_id: 14, name: "HR_HEAD", code: "HR_HEAD" }]}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("regular-task-template-filter-role")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("regular-task-template-filter-role"), {
      target: { value: "14" },
    });

    expect(onChange).toHaveBeenCalledWith({ executor_role_id: 14 });
  });
});
