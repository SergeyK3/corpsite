import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PositionsPageClient from "./PositionsPageClient";

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

    const call = apiFetchJson.mock.calls.at(-1);
    expect(call?.[0]).toBe("/directory/positions");
    expect(call?.[1]?.query?.scope).toBe("allowed");
    expect(screen.getByTestId("positions-scope-allowed")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Режим: Разрешённые")).toBeInTheDocument();
  });

  it("requests used scope when toggled", async () => {
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

    const call = apiFetchJson.mock.calls.at(-1);
    expect(call?.[1]?.query?.scope).toBe("used");
    expect(screen.getByTestId("positions-scope-used")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Режим: Используемые")).toBeInTheDocument();
  });

  it("updates URL and reloads when switching scope mode", async () => {
    apiFetchJson.mockResolvedValue({ items: [], total: 0 });

    render(<PositionsPageClient />);

    await waitFor(() => {
      expect(screen.getByTestId("positions-scope-toggle")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("positions-scope-used"));

    expect(replace).toHaveBeenCalledWith(
      "/directory/positions?org_group_id=3&org_unit_id=74&position_scope=used",
    );
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
});
