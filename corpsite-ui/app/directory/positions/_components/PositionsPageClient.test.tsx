import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PositionsPageClient, { buildPositionsListQuery } from "./PositionsPageClient";

const replace = vi.fn();
let searchParams = new URLSearchParams("org_group_id=3&org_unit_id=74");

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/directory/positions",
  useSearchParams: () => searchParams,
}));

vi.mock("@/components/OrgScopeFilter", () => ({
  default: () => <div data-testid="mock-org-scope-filter" />,
}));

vi.mock("@/components/OrgUnitScopeFilter", () => ({
  default: () => <div data-testid="mock-org-unit-scope-filter" />,
}));

const apiFetchJson = vi.fn();

vi.mock("../../../../lib/api", () => ({
  apiFetchJson: (...args: unknown[]) => apiFetchJson(...args),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  searchParams = new URLSearchParams("org_group_id=3&org_unit_id=74");
});

function lastFetchQuery(): Record<string, unknown> | undefined {
  const call = apiFetchJson.mock.calls.at(-1);
  return call?.[1]?.query as Record<string, unknown> | undefined;
}

function fetchScopesAfterCallIndex(index: number): string[] {
  return apiFetchJson.mock.calls
    .slice(index)
    .map((call) => String((call?.[1] as { query?: { scope?: string } })?.query?.scope ?? ""));
}

const USED_FIXTURE = {
  items: [
    { position_id: 1, name: "Архивариус" },
    { position_id: 2, name: "Руководитель отдела кадров" },
  ],
  total: 2,
};

const ALLOWED_FIXTURE = {
  items: [
    { position_id: 10, name: "Руководитель отдела кадров" },
    { position_id: 11, name: "Менеджер УЧР" },
    { position_id: 12, name: "Менеджер" },
    { position_id: 13, name: "секретарь-референт" },
    { position_id: 14, name: "Переводчик казахского языка" },
  ],
  total: 5,
};

describe("buildPositionsListQuery", () => {
  it("includes org_unit_id and scope=allowed for selected unit by default", () => {
    expect(
      buildPositionsListQuery({
        orgGroupId: 3,
        orgUnitId: 74,
        positionScope: "allowed",
      }),
    ).toEqual({
      limit: 50,
      offset: 0,
      org_unit_id: 74,
      scope: "allowed",
    });
  });

  it("omits org_group_id when org_unit_id is selected", () => {
    const query = buildPositionsListQuery({
      orgGroupId: 3,
      orgUnitId: 74,
      positionScope: "allowed",
    });
    expect(query).not.toHaveProperty("org_group_id");
  });

  it("includes org_unit_id and scope=used when used mode is selected", () => {
    expect(
      buildPositionsListQuery({
        orgUnitId: 74,
        positionScope: "used",
      }),
    ).toEqual({
      limit: 50,
      offset: 0,
      org_unit_id: 74,
      scope: "used",
    });
  });

  it("returns global query without scope when unit is not selected", () => {
    expect(buildPositionsListQuery({ orgGroupId: 3 })).toEqual({
      limit: 50,
      offset: 0,
      org_group_id: 3,
    });
  });

  it("does not send scope without org_unit_id", () => {
    const query = buildPositionsListQuery({
      orgGroupId: 3,
      positionScope: "allowed",
    });
    expect(query).not.toHaveProperty("scope");
    expect(query).not.toHaveProperty("org_unit_id");
  });
});

describe("PositionsPageClient position scope", () => {
  it("defaults to allowed scope when org unit is selected", async () => {
    apiFetchJson.mockResolvedValue({
      items: [{ position_id: 1, name: "Менеджер" }],
      total: 1,
    });

    render(<PositionsPageClient />);

    await waitFor(() => {
      expect(apiFetchJson).toHaveBeenCalled();
    });

    expect(lastFetchQuery()?.org_unit_id).toBe(74);
    expect(lastFetchQuery()?.scope).toBe("allowed");
    expect(lastFetchQuery()).not.toHaveProperty("org_group_id");
    expect(screen.getByTestId("positions-scope-allowed")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Режим: Разрешённые")).toBeInTheDocument();
  });

  it("requests used scope when toggled in URL", async () => {
    searchParams = new URLSearchParams(
      "org_group_id=3&org_unit_id=74&position_scope=used",
    );
    apiFetchJson.mockResolvedValue({
      items: [{ position_id: 2, name: "Архивариус" }],
      total: 1,
    });

    render(<PositionsPageClient />);

    await waitFor(() => {
      expect(apiFetchJson).toHaveBeenCalled();
    });

    expect(lastFetchQuery()?.org_unit_id).toBe(74);
    expect(lastFetchQuery()?.scope).toBe("used");
    expect(screen.getByTestId("positions-scope-used")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Режим: Используемые")).toBeInTheDocument();
  });

  it("uses global URL without scope when no unit is selected", async () => {
    searchParams = new URLSearchParams("");
    apiFetchJson.mockResolvedValue({ items: [], total: 0 });

    render(<PositionsPageClient />);

    await waitFor(() => {
      expect(apiFetchJson).toHaveBeenCalled();
    });

    expect(lastFetchQuery()).toEqual({ limit: 50, offset: 0 });
    expect(screen.queryByTestId("positions-scope-toggle")).not.toBeInTheDocument();
  });

  it("shows hint instead of allowed toggle when only group is selected", async () => {
    searchParams = new URLSearchParams("org_group_id=3");
    apiFetchJson.mockResolvedValue({ items: [], total: 0 });

    render(<PositionsPageClient />);

    await waitFor(() => {
      expect(apiFetchJson).toHaveBeenCalled();
    });

    expect(lastFetchQuery()).toEqual({
      limit: 50,
      offset: 0,
      org_group_id: 3,
    });
    expect(screen.getByTestId("positions-scope-hint")).toHaveTextContent("Выберите подразделение");
    expect(screen.queryByTestId("positions-scope-toggle")).not.toBeInTheDocument();
    expect(screen.queryByText("Режим: Разрешённые")).not.toBeInTheDocument();
  });

  it("updates URL and reloads when switching scope mode", async () => {
    apiFetchJson.mockResolvedValue({ items: [], total: 0 });

    render(<PositionsPageClient />);

    await waitFor(() => {
      expect(screen.getByTestId("positions-scope-toggle")).toBeInTheDocument();
    });

    const callsBefore = apiFetchJson.mock.calls.length;
    apiFetchJson.mockClear();
    apiFetchJson.mockResolvedValue({
      items: [{ position_id: 9, name: "Менеджер" }],
      total: 1,
    });

    fireEvent.click(screen.getByTestId("positions-scope-used"));

    expect(replace).toHaveBeenCalledWith(
      "/directory/positions?org_group_id=3&org_unit_id=74&position_scope=used",
    );

    await waitFor(() => {
      expect(apiFetchJson).toHaveBeenCalled();
    });

    const scopesAfterClick = fetchScopesAfterCallIndex(0);
    expect(scopesAfterClick).toContain("used");
    expect(scopesAfterClick.filter((scope) => scope === "allowed")).toHaveLength(0);
    expect(lastFetchQuery()?.org_unit_id).toBe(74);
    expect(lastFetchQuery()).not.toHaveProperty("org_group_id");
    expect(callsBefore).toBeGreaterThan(0);
  });

  it("switches used to allowed while URL still has position_scope=used", async () => {
    searchParams = new URLSearchParams(
      "org_group_id=3&org_unit_id=73&position_scope=used",
    );
    apiFetchJson.mockResolvedValueOnce(USED_FIXTURE);

    render(<PositionsPageClient />);

    await waitFor(() => {
      expect(screen.getByText("Архивариус")).toBeInTheDocument();
    });
    expect(screen.getByTestId("positions-scope-used")).toHaveAttribute("aria-pressed", "true");

    const callsBeforeClick = apiFetchJson.mock.calls.length;
    apiFetchJson.mockClear();
    apiFetchJson.mockImplementation(async (_path, opts) => {
      const scope = String((opts as { query?: { scope?: string } })?.query?.scope ?? "");
      if (scope === "allowed") return ALLOWED_FIXTURE;
      return USED_FIXTURE;
    });

    fireEvent.click(screen.getByTestId("positions-scope-allowed"));

    await waitFor(() => {
      expect(screen.getByText("Переводчик казахского языка")).toBeInTheDocument();
    });

    const scopesAfterClick = fetchScopesAfterCallIndex(0);
    expect(scopesAfterClick).toContain("allowed");
    expect(scopesAfterClick.filter((scope) => scope === "used")).toHaveLength(0);

    expect(screen.queryByText("Архивариус")).not.toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(6);
    expect(screen.getByText("Всего: 5")).toBeInTheDocument();
    expect(screen.getByTestId("positions-scope-allowed")).toHaveAttribute("aria-pressed", "true");
    expect(replace).toHaveBeenCalledWith(
      "/directory/positions?org_group_id=3&org_unit_id=73&position_scope=allowed",
    );
    expect(lastFetchQuery()?.scope).toBe("allowed");
    expect(lastFetchQuery()?.org_unit_id).toBe(73);
    expect(callsBeforeClick).toBeGreaterThan(0);
  });

  it("switches allowed to used and shows used positions", async () => {
    searchParams = new URLSearchParams(
      "org_group_id=3&org_unit_id=73&position_scope=allowed",
    );
    apiFetchJson.mockResolvedValueOnce(ALLOWED_FIXTURE);

    render(<PositionsPageClient />);

    await waitFor(() => {
      expect(screen.getByText("Менеджер УЧР")).toBeInTheDocument();
    });

    apiFetchJson.mockClear();
    apiFetchJson.mockImplementation(async (_path, opts) => {
      const scope = String((opts as { query?: { scope?: string } })?.query?.scope ?? "");
      return scope === "used" ? USED_FIXTURE : ALLOWED_FIXTURE;
    });

    fireEvent.click(screen.getByTestId("positions-scope-used"));

    await waitFor(() => {
      expect(screen.getByText("Архивариус")).toBeInTheDocument();
    });

    const scopesAfterClick = fetchScopesAfterCallIndex(0);
    expect(scopesAfterClick).toContain("used");
    expect(scopesAfterClick.filter((scope) => scope === "allowed")).toHaveLength(0);
    expect(screen.getByTestId("positions-scope-used")).toHaveAttribute("aria-pressed", "true");
    expect(replace).toHaveBeenCalledWith(
      "/directory/positions?org_group_id=3&org_unit_id=73&position_scope=used",
    );
  });

  it("keeps allowed table when a stale used response arrives after switching", async () => {
    searchParams = new URLSearchParams(
      "org_group_id=3&org_unit_id=73&position_scope=used",
    );

    let resolveInitialUsed: (value: unknown) => void = () => {};
    let resolveAllowed: (value: unknown) => void = () => {};
    const initialUsedPromise = new Promise((resolve) => {
      resolveInitialUsed = resolve;
    });
    const allowedPromise = new Promise((resolve) => {
      resolveAllowed = resolve;
    });

    apiFetchJson.mockImplementation((_path, opts) => {
      const scope = String((opts as { query?: { scope?: string } })?.query?.scope ?? "");
      if (scope === "allowed") return allowedPromise;
      return initialUsedPromise;
    });

    render(<PositionsPageClient />);

    fireEvent.click(screen.getByTestId("positions-scope-allowed"));

    resolveAllowed(ALLOWED_FIXTURE);

    await waitFor(() => {
      expect(screen.getByText("Переводчик казахского языка")).toBeInTheDocument();
    });
    expect(screen.queryByText("Архивариус")).not.toBeInTheDocument();

    resolveInitialUsed(USED_FIXTURE);

    await waitFor(() => {
      expect(apiFetchJson.mock.calls.length).toBeGreaterThanOrEqual(2);
    });

    expect(screen.getByText("Переводчик казахского языка")).toBeInTheDocument();
    expect(screen.queryByText("Архивариус")).not.toBeInTheDocument();
    expect(screen.getByText("Всего: 5")).toBeInTheDocument();
  });

  it("refresh button repeats the current scoped request", async () => {
    apiFetchJson.mockResolvedValue({
      items: [{ position_id: 1, name: "Менеджер" }],
      total: 1,
    });

    render(<PositionsPageClient />);

    await waitFor(() => {
      expect(apiFetchJson).toHaveBeenCalledTimes(1);
    });

    apiFetchJson.mockClear();
    apiFetchJson.mockResolvedValue({
      items: [{ position_id: 1, name: "Менеджер" }],
      total: 1,
    });

    fireEvent.click(screen.getByRole("button", { name: "Обновить" }));

    await waitFor(() => {
      expect(apiFetchJson).toHaveBeenCalledTimes(1);
    });

    expect(lastFetchQuery()?.org_unit_id).toBe(74);
    expect(lastFetchQuery()?.scope).toBe("allowed");
    expect(lastFetchQuery()).not.toHaveProperty("org_group_id");
  });

  it("does not let a late global response overwrite scoped table state", async () => {
    searchParams = new URLSearchParams("");

    let resolveGlobal: (value: unknown) => void = () => {};
    let resolveScoped: (value: unknown) => void = () => {};

    const globalPromise = new Promise((resolve) => {
      resolveGlobal = resolve;
    });
    const scopedPromise = new Promise((resolve) => {
      resolveScoped = resolve;
    });

    apiFetchJson
      .mockImplementationOnce(() => globalPromise)
      .mockImplementationOnce(() => scopedPromise);

    const { rerender } = render(<PositionsPageClient />);

    searchParams = new URLSearchParams("org_group_id=3&org_unit_id=74&position_scope=allowed");
    rerender(<PositionsPageClient />);

    resolveScoped({
      items: [
        { position_id: 11, name: "HR 1" },
        { position_id: 12, name: "HR 2" },
        { position_id: 13, name: "HR 3" },
        { position_id: 14, name: "HR 4" },
        { position_id: 15, name: "HR 5" },
      ],
      total: 5,
    });

    await waitFor(() => {
      expect(screen.getByText("HR 5")).toBeInTheDocument();
    });

    resolveGlobal({ items: [], total: 0 });

    await waitFor(() => {
      expect(apiFetchJson).toHaveBeenCalledTimes(2);
    });

    expect(screen.getByText("HR 5")).toBeInTheDocument();
    expect(screen.getByText("Всего: 5")).toBeInTheDocument();
  });

  it("displays all 5 HR allowed positions from scoped response", async () => {
    apiFetchJson.mockResolvedValue({
      items: [
        { position_id: 101, name: "Директор" },
        { position_id: 102, name: "Менеджер УЧР" },
        { position_id: 103, name: "Кадровик" },
        { position_id: 104, name: "Специалист" },
        { position_id: 105, name: "Секретарь" },
      ],
      total: 5,
      filter_org_unit_id: 74,
      filter_org_unit_name: "Отдел кадров",
    });

    render(<PositionsPageClient />);

    await waitFor(() => {
      expect(screen.getByText("Секретарь")).toBeInTheDocument();
    });

    expect(screen.getAllByRole("row")).toHaveLength(6);
    expect(screen.getByText("Всего: 5")).toBeInTheDocument();
    expect(lastFetchQuery()?.org_unit_id).toBe(74);
    expect(lastFetchQuery()?.scope).toBe("allowed");
    expect(lastFetchQuery()).not.toHaveProperty("org_group_id");
  });

  it("shows allowed position without requiring an employee assignment", async () => {
    apiFetchJson.mockResolvedValue({
      items: [{ position_id: 11, name: "Менеджер УЧР" }],
      total: 1,
    });

    render(<PositionsPageClient />);

    await waitFor(() => {
      expect(screen.getByText("Менеджер УЧР")).toBeInTheDocument();
    });
  });

  it("syncs position_scope=allowed into URL when unit is selected without scope param", async () => {
    searchParams = new URLSearchParams("org_group_id=3&org_unit_id=74");
    apiFetchJson.mockResolvedValue({ items: [], total: 0 });

    render(<PositionsPageClient />);

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith(
        "/directory/positions?org_group_id=3&org_unit_id=74&position_scope=allowed",
      );
    });
  });
});
