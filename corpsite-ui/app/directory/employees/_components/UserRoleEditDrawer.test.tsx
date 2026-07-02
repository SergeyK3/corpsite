import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import UserRoleEditDrawer from "./UserRoleEditDrawer";

vi.mock("@/lib/platformRoleCatalog", () => ({
  listPlatformRoleCatalog: vi.fn().mockResolvedValue([
    { id: 5, label: "QM Head", code: "QM_HEAD" },
    { id: 8, label: "HR Head", code: "HR_HEAD" },
  ]),
}));

describe("UserRoleEditDrawer", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows login, current role, and saves selected role", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    render(
      <UserRoleEditDrawer
        open
        login="makibaeva.as"
        currentRoleId={5}
        currentRoleLabel="Руководитель ОВЭиПД"
        onClose={onClose}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByText("makibaeva.as")).toBeInTheDocument();
    expect(screen.getByText("Руководитель ОВЭиПД")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole("option", { name: /HR_HEAD/i })).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/Новая роль Corpsite/i), { target: { value: "8" } });
    fireEvent.click(screen.getByRole("button", { name: "Сохранить" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(8);
    });
  });
});
