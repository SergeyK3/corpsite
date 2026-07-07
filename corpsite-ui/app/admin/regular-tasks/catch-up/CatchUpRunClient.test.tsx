// FILE: corpsite-ui/app/admin/regular-tasks/catch-up/CatchUpRunClient.test.tsx

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetchJson } from "@/lib/api";
import { catchUpUiLabel } from "@/lib/i18n";

import CatchUpRunClient from "./CatchUpRunClient";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
  usePathname: () => "/admin/regular-tasks/catch-up",
  useSearchParams: () => new URLSearchParams("org_unit_id=44&org_group_id=1"),
}));

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

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

vi.mock("@/lib/api", () => ({
  apiFetchJson: vi.fn(async (path: string) => {
    if (path === "/regular-tasks") {
      return {
        items: [
          {
            regular_task_id: 12,
            title: "HR monthly",
            executor_role_id: 14,
            executor_role_name: "HR_HEAD",
            executor_role_code: "HR_HEAD",
            is_active: true,
          },
        ],
      };
    }
    return {};
  }),
  apiCatchUpRegularTasks: vi.fn(),
  apiGetRegularTaskRunItems: vi.fn(async () => ({ items: [] })),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("CatchUpRunClient form layout", () => {
  beforeEach(() => {
    render(<CatchUpRunClient />);
  });

  it("renders periodicity before period field in DOM order", () => {
    const grid = screen.getByTestId("catch-up-form-grid");
    const testIds = within(grid)
      .getAllByRole("combobox")
      .map((el) => el.getAttribute("data-testid"))
      .filter(Boolean);

    expect(testIds.indexOf("catch-up-schedule-type")).toBeLessThan(
      testIds.indexOf("catch-up-period-select"),
    );
  });

  it("uses unified template filters bar instead of legacy catch-up org selects", () => {
    expect(screen.getByTestId("regular-task-template-filters")).toBeInTheDocument();
    expect(screen.getByTestId("regular-task-template-filter-group")).toBeInTheDocument();
    expect(screen.getByTestId("regular-task-template-filter-unit")).toBeInTheDocument();
    expect(screen.getByTestId("regular-task-template-filter-role")).toBeInTheDocument();
    expect(screen.queryByTestId("catch-up-org-group")).not.toBeInTheDocument();
    expect(screen.queryByTestId("catch-up-org-unit")).not.toBeInTheDocument();
    expect(screen.queryByTestId("catch-up-executor")).not.toBeInTheDocument();
  });

  it("changes period options when periodicity changes", () => {
    const periodSelect = screen.getByTestId("catch-up-period-select") as HTMLSelectElement;
    const weeklyFirst = periodSelect.options[0]?.textContent ?? "";

    fireEvent.change(screen.getByTestId("catch-up-schedule-type"), { target: { value: "monthly" } });

    const monthlyFirst = (screen.getByTestId("catch-up-period-select") as HTMLSelectElement).options[0]
      ?.textContent;
    expect(monthlyFirst).not.toBe(weeklyFirst);
    expect(monthlyFirst).toMatch(/\d{4}/);
  });

  it("weekly period options display DD.MM–DD.MM range", () => {
    const periodSelect = screen.getByTestId("catch-up-period-select") as HTMLSelectElement;
    expect(periodSelect.options[0]?.textContent).toMatch(/\d{2}\.\d{2}–\d{2}\.\d{2}/);
  });
});

describe("CatchUpRunClient org scope and template loading", () => {
  beforeEach(() => {
    vi.mocked(apiFetchJson).mockClear();
    replaceMock.mockClear();
    render(<CatchUpRunClient />);
  });

  it("strips legacy org scope params from URL on mount", async () => {
    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith("/admin/regular-tasks/catch-up");
    });
  });

  it("loads templates without org scope by default", async () => {
    await waitFor(() => {
      expect(apiFetchJson).toHaveBeenCalledWith(
        "/regular-tasks",
        expect.objectContaining({
          query: expect.objectContaining({
            status: "active",
            schedule_type: "weekly",
            limit: 200,
            offset: 0,
          }),
        }),
      );
    });

    const calls = vi.mocked(apiFetchJson).mock.calls.filter(([path]) => path === "/regular-tasks");
    const lastQuery = calls.at(-1)?.[1]?.query as Record<string, unknown>;
    expect(lastQuery.org_group_id).toBeUndefined();
    expect(lastQuery.org_unit_id).toBeUndefined();
    expect(lastQuery.executor_role_id).toBeUndefined();
  });

  it("passes explicit org filters to template list API", async () => {
    await waitFor(() => {
      expect(screen.getByTestId("regular-task-template-filter-unit")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("regular-task-template-filter-group"), {
      target: { value: "3" },
    });
    fireEvent.change(screen.getByTestId("regular-task-template-filter-unit"), {
      target: { value: "73" },
    });

    await waitFor(() => {
      expect(apiFetchJson).toHaveBeenCalledWith(
        "/regular-tasks",
        expect.objectContaining({
          query: expect.objectContaining({
            org_group_id: 3,
            org_unit_id: 73,
            schedule_type: "weekly",
          }),
        }),
      );
    });
  });

  it("requests monthly templates when periodicity is switched to monthly", async () => {
    fireEvent.change(screen.getByTestId("catch-up-schedule-type"), { target: { value: "monthly" } });

    await waitFor(() => {
      expect(apiFetchJson).toHaveBeenCalledWith(
        "/regular-tasks",
        expect.objectContaining({
          query: expect.objectContaining({
            schedule_type: "monthly",
          }),
        }),
      );
    });
  });

  it("keeps manually selected periodicity when period changes", async () => {
    fireEvent.change(screen.getByTestId("catch-up-schedule-type"), { target: { value: "yearly" } });

    await waitFor(() => {
      expect((screen.getByTestId("catch-up-schedule-type") as HTMLSelectElement).value).toBe("yearly");
    });

    const periodSelect = screen.getByTestId("catch-up-period-select") as HTMLSelectElement;
    if (periodSelect.options.length > 1) {
      fireEvent.change(periodSelect, { target: { value: periodSelect.options[1].value } });
    }

    expect((screen.getByTestId("catch-up-schedule-type") as HTMLSelectElement).value).toBe("yearly");
  });
});

describe("CatchUpRunClient filter labels", () => {
  it("shows executor role filter with unified label", async () => {
    render(<CatchUpRunClient />);
    await waitFor(() => {
      expect(screen.getByText("Должность / роль исполнителя")).toBeInTheDocument();
    });
    await waitFor(() => {
      const roleSelect = screen.getByTestId("regular-task-template-filter-role") as HTMLSelectElement;
      const labels = Array.from(roleSelect.options).map((opt) => opt.text);
      expect(labels).toContain("HR_HEAD");
    });
    expect(catchUpUiLabel("regular_task_id")).toBeTruthy();
  });
});
