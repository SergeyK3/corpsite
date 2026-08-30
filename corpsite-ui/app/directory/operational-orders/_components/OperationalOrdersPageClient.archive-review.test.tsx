import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiAuthMe } from "@/lib/api";

import { listArchiveReview, listDocuments, listWorkspaces } from "../_lib/api";
import OperationalOrdersPageClient from "./OperationalOrdersPageClient";

const replace = vi.fn();
let searchParamsValue = "tab=archive-review";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => new URLSearchParams(searchParamsValue),
}));

vi.mock("@/lib/api", () => ({ apiAuthMe: vi.fn() }));
vi.mock("@/components/TaskOrgFiltersBar", () => ({ default: () => <div data-testid="org-filters" /> }));
vi.mock("./WorkspacesTable", () => ({
  default: ({ items }: { items: Array<{ proposed_title: string | null }> }) => (
    <div data-testid="workspace-items">{items.map((item) => item.proposed_title).join(",")}</div>
  ),
}));
vi.mock("../_lib/api", () => ({
  OO_BASE_PATH: "/directory/operational-orders",
  listArchiveReview: vi.fn(),
  listDocuments: vi.fn(),
  listWorkspaces: vi.fn(),
  mapOoApiError: (_error: unknown, fallback: string) => fallback,
}));

beforeEach(() => {
  searchParamsValue = "tab=archive-review";
  vi.mocked(apiAuthMe).mockResolvedValue({ user_id: 25, has_operational_orders_read: true });
  vi.mocked(listWorkspaces).mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
  vi.mocked(listDocuments).mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
  vi.mocked(listArchiveReview).mockResolvedValue({
    batch: null,
    stats: null,
    sections: [],
    items: [],
    total: 0,
    limit: 25,
    offset: 0,
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("OperationalOrdersPageClient archive-review tab", () => {
  it("renders the third tab without loading official workspaces or documents", async () => {
    render(<OperationalOrdersPageClient />);

    expect(await screen.findByRole("tab", { name: "Рабочие проекты" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Официальные документы" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Архив на проверке", selected: true })).toBeTruthy();
    expect(await screen.findByTestId("archive-review-no-batch")).toBeTruthy();
    expect(screen.queryByTestId("org-filters")).toBeNull();
    expect(listArchiveReview).toHaveBeenCalled();
    expect(listWorkspaces).not.toHaveBeenCalled();
    expect(listDocuments).not.toHaveBeenCalled();
  });

  it("allows a specialized reviewer to see only the archive tab", async () => {
    vi.mocked(apiAuthMe).mockResolvedValue({
      user_id: 8,
      has_operational_orders_read: false,
      operational_orders_permissions: { archive_review: true } as never,
    });

    render(<OperationalOrdersPageClient />);

    expect(await screen.findByTestId("archive-review-no-batch")).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Архив на проверке", selected: true })).toBeTruthy();
    expect(screen.queryByRole("tab", { name: "Рабочие проекты" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Официальные документы" })).toBeNull();
    expect(listWorkspaces).not.toHaveBeenCalled();
    expect(listDocuments).not.toHaveBeenCalled();
  });

  it("ignores a stale workspace response after switching tabs", async () => {
    searchParamsValue = "tab=workspaces";
    let resolveFirst!: (value: Awaited<ReturnType<typeof listWorkspaces>>) => void;
    const first = new Promise<Awaited<ReturnType<typeof listWorkspaces>>>((resolve) => {
      resolveFirst = resolve;
    });
    vi.mocked(listWorkspaces)
      .mockReset()
      .mockReturnValueOnce(first)
      .mockReturnValueOnce(new Promise(() => {}));

    const view = render(<OperationalOrdersPageClient />);
    await waitFor(() => expect(listWorkspaces).toHaveBeenCalledTimes(1));

    searchParamsValue = "tab=archive-review";
    view.rerender(<OperationalOrdersPageClient />);
    expect(await screen.findByTestId("archive-review-no-batch")).toBeTruthy();

    await act(async () => {
      resolveFirst({
        items: [{ proposed_title: "Устаревший проект" } as never],
        total: 1,
        limit: 100,
        offset: 0,
      });
    });
    searchParamsValue = "tab=workspaces";
    view.rerender(<OperationalOrdersPageClient />);
    await waitFor(() => expect(listWorkspaces).toHaveBeenCalledTimes(2));
    expect(screen.getByTestId("workspace-items").textContent).not.toContain("Устаревший проект");
  });

  it("redirects a specialized reviewer before requesting a forbidden direct tab", async () => {
    searchParamsValue = "tab=workspaces";
    vi.mocked(apiAuthMe).mockResolvedValue({
      user_id: 8,
      has_operational_orders_read: false,
      operational_orders_permissions: { archive_review: true } as never,
    });

    render(<OperationalOrdersPageClient />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith(
      "/directory/operational-orders?tab=archive-review",
    ));
    expect(listWorkspaces).not.toHaveBeenCalled();
    expect(listDocuments).not.toHaveBeenCalled();
  });
});
