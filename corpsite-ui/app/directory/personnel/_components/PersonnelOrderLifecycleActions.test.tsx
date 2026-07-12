import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelOrderLifecycleActions from "./PersonnelOrderLifecycleActions";
import type { PersonnelOrderDetailResponse, PersonnelOrderHeader } from "../_lib/personnelOrdersApi.client";

vi.mock("@/lib/api", () => ({
  apiAuthMe: vi.fn(async () => ({
    user_id: 7,
    has_personnel_orders_archive: true,
    has_personnel_orders_restore: true,
  })),
}));

const baseOrder: PersonnelOrderHeader = {
  order_id: 55,
  order_number: "55-К",
  order_date: "2026-07-12",
  order_type_code: "HIRE",
  order_class: "PERSONNEL",
  status: "REGISTERED",
  source_mode: "PAPER",
  created_by: 1,
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelOrderLifecycleActions archive buttons", () => {
  it("shows archive button for archivable order with permission", async () => {
    render(
      <PersonnelOrderLifecycleActions
        order={baseOrder}
        itemCount={1}
        linkedEventCount={0}
        onChanged={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-archive-button")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("personnel-order-restore-button")).not.toBeInTheDocument();
  });

  it("shows restore button for archived order with permission", async () => {
    render(
      <PersonnelOrderLifecycleActions
        order={{ ...baseOrder, is_archived: true }}
        itemCount={1}
        linkedEventCount={0}
        onChanged={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("personnel-order-restore-button")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("personnel-order-archive-button")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Аннулировать" })).not.toBeInTheDocument();
  });

  it("hides lifecycle actions for archived order without restore permission", async () => {
    const { apiAuthMe } = await import("@/lib/api");
    vi.mocked(apiAuthMe).mockResolvedValueOnce({
      user_id: 7,
      has_personnel_orders_archive: false,
      has_personnel_orders_restore: false,
    });

    render(
      <PersonnelOrderLifecycleActions
        order={{ ...baseOrder, is_archived: true }}
        itemCount={1}
        linkedEventCount={0}
        onChanged={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(apiAuthMe).toHaveBeenCalled();
    });
    expect(screen.queryByTestId("personnel-order-restore-button")).not.toBeInTheDocument();
    expect(screen.queryByTestId("personnel-order-archive-button")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Аннулировать" })).not.toBeInTheDocument();
  });

  it("keeps void button for active registered order", async () => {
    render(
      <PersonnelOrderLifecycleActions
        order={baseOrder}
        itemCount={1}
        linkedEventCount={0}
        onChanged={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Аннулировать" })).toBeInTheDocument();
    });
    expect(screen.getByTestId("personnel-order-archive-button")).toBeInTheDocument();
  });
});
