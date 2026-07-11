import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelOrderDetailDrawer from "./PersonnelOrderDetailDrawer";
import type { PersonnelOrderDetailResponse } from "../_lib/personnelOrdersApi.client";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/directory/personnel/orders",
  useSearchParams: () => new URLSearchParams(""),
}));

vi.mock("@/components/OrgScopeFilter", () => ({
  default: () => <div data-testid="mock-org-scope-filter" />,
}));

vi.mock("@/app/directory/employees/_lib/api.client", () => ({
  getEmployees: vi.fn(async () => ({ items: [] })),
}));

vi.mock("@/lib/taskOrgFilters", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/taskOrgFilters")>();
  return {
    ...actual,
    loadScopedPositionOptions: vi.fn(async () => []),
  };
});

vi.mock("../_lib/personnelOrdersApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelOrdersApi.client")>(
    "../_lib/personnelOrdersApi.client",
  );
  return {
    ...actual,
    getPersonnelOrder: vi.fn(),
    getPersonnelOrderEditorial: vi.fn(async () => ({
      order_id: 42,
      order_status: "DRAFT",
      editable: true,
      order_blocks: [],
      items: [],
    })),
    generatePersonnelOrderEditorial: vi.fn(async () => ({
      order_id: 42,
      order_status: "DRAFT",
      editable: true,
      order_blocks: [],
      items: [],
    })),
  };
});

import { getPersonnelOrder } from "../_lib/personnelOrdersApi.client";

const detail: PersonnelOrderDetailResponse = {
  order: {
    order_id: 42,
    order_number: "12-К",
    order_date: "2026-07-10",
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
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelOrderDetailDrawer print entry", () => {
  it("shows exactly one Печать button that opens the language dialog, and keeps Аннулировать", async () => {
    vi.mocked(getPersonnelOrder).mockResolvedValue(detail);

    render(<PersonnelOrderDetailDrawer orderId={42} open onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-drawer-print")).toBeInTheDocument();
    });

    const printButtons = screen.getAllByRole("button", { name: "Печать" });
    expect(printButtons).toHaveLength(1);
    expect(printButtons[0]).toHaveAttribute("data-testid", "personnel-order-drawer-print");
    expect(screen.queryByTestId("personnel-order-actions-print")).not.toBeInTheDocument();

    expect(screen.getByRole("button", { name: "Аннулировать" })).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("personnel-order-drawer-print"));
    expect(screen.getByTestId("personnel-order-print-language-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-order-print-open")).toHaveTextContent("Предпросмотр");
    expect(screen.getByTestId("personnel-order-pdf-open")).toHaveTextContent("Открыть PDF");
  });
});
