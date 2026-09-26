import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { fetchAccessGrants, fetchAccessRoles, fetchGuardMode } = vi.hoisted(() => ({
  fetchAccessGrants: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  fetchAccessRoles: vi.fn().mockResolvedValue([{ access_role_id: 1, code: "USER_ACCESS_ADMIN", label: "Управление доступом", access_level: "ADMIN" }]),
  fetchGuardMode: vi.fn().mockResolvedValue({ shadow_mode: false, enforcement_active: false }),
}));

vi.mock("../../_lib/adminSystemApi.client", () => ({
  createAccessGrant: vi.fn(), fetchAccessGrants, fetchAccessRoles,
  fetchEffectiveAccessUser: vi.fn(), fetchGuardMode,
  mapAdminSystemApiError: vi.fn(() => "Ошибка"), revokeAccessGrant: vi.fn(),
  formatAccessRoleLabel: vi.fn((role) => role.label),
}));
vi.mock("../shared/PersonnelUserTargetSearch", () => ({ default: () => <div data-testid="personnel-user-target-search" /> }));
vi.mock("../shared/TargetSearchField", () => ({ default: () => <div data-testid="generic-target-search" /> }));

import AccessTab from "./AccessTab";

describe("AccessTab recipient search", () => {
  it("shows personnel filters only for existing USER recipients and retains generic search for other target types", async () => {
    render(<AccessTab />);
    expect(await screen.findByTestId("personnel-user-target-search")).toBeInTheDocument();
    expect(screen.queryByTestId("generic-target-search")).not.toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue("USER"), { target: { value: "EMPLOYEE" } });
    expect(screen.queryByTestId("personnel-user-target-search")).not.toBeInTheDocument();
    expect(screen.getByTestId("generic-target-search")).toBeInTheDocument();
  });
});
