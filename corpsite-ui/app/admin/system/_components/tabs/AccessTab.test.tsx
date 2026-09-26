import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { createAccessGrant, fetchAccessGrants, fetchAccessRoles, fetchGuardMode } = vi.hoisted(() => ({
  createAccessGrant: vi.fn().mockResolvedValue({}),
  fetchAccessGrants: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  fetchAccessRoles: vi.fn().mockResolvedValue([{ access_role_id: 1, code: "USER_ACCESS_ADMIN", label: "Управление доступом", access_level: "ADMIN" }]),
  fetchGuardMode: vi.fn().mockResolvedValue({ shadow_mode: false, enforcement_active: false }),
}));

vi.mock("../../_lib/adminSystemApi.client", () => ({
  createAccessGrant, fetchAccessGrants, fetchAccessRoles,
  fetchEffectiveAccessUser: vi.fn(), fetchGuardMode,
  mapAdminSystemApiError: vi.fn(() => "Ошибка"), revokeAccessGrant: vi.fn(),
  formatAccessRoleLabel: vi.fn((role) => role.label),
}));
vi.mock("../shared/PersonnelUserTargetSearch", () => ({
  default: ({ onChange }: { onChange: (target: { target_type: string; target_id: number }) => void }) => (
    <button type="button" data-testid="personnel-user-target-search" onClick={() => onChange({ target_type: "USER", target_id: 99 })}>
      select technical account
    </button>
  ),
}));
vi.mock("../shared/TargetSearchField", () => ({ default: () => <div data-testid="generic-target-search" /> }));

import AccessTab from "./AccessTab";

afterEach(() => cleanup());

describe("AccessTab recipient search", () => {
  it("shows personnel filters only for existing USER recipients and retains generic search for other target types", async () => {
    render(<AccessTab />);
    expect(await screen.findByTestId("personnel-user-target-search")).toBeInTheDocument();
    expect(screen.queryByTestId("generic-target-search")).not.toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue("USER"), { target: { value: "EMPLOYEE" } });
    expect(screen.queryByTestId("personnel-user-target-search")).not.toBeInTheDocument();
    expect(screen.getByTestId("generic-target-search")).toBeInTheDocument();
  });

  it("uses a selected technical USER id when granting USER_ACCESS_ADMIN", async () => {
    render(<AccessTab />);
    fireEvent.click(await screen.findByTestId("personnel-user-target-search"));
    fireEvent.click(screen.getByRole("button", { name: /Создать grant/i }));

    await waitFor(() => expect(createAccessGrant).toHaveBeenCalledWith(expect.objectContaining({
      access_role_id: 1,
      target_type: "USER",
      target_id: 99,
    })));
  });
});
