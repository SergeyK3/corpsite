import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { createAccessGrant, fetchAccessGrants, fetchAccessRoles, fetchGuardMode, fetchAccessPeople, fetchAccessPerson } = vi.hoisted(() => ({
  createAccessGrant: vi.fn().mockResolvedValue({}),
  fetchAccessGrants: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  fetchAccessRoles: vi.fn().mockResolvedValue([{ access_role_id: 1, code: "USER_ACCESS_ADMIN", label: "Управление доступом", access_level: "ADMIN" }]),
  fetchGuardMode: vi.fn().mockResolvedValue({ shadow_mode: false, enforcement_active: false }),
  fetchAccessPeople: vi.fn().mockResolvedValue({ items: [], unlinked_accounts: [] }),
  fetchAccessPerson: vi.fn().mockResolvedValue({ items: [], implicit_sources: [], coverage_note: "" }),
}));

vi.mock("../../_lib/adminSystemApi.client", () => ({
  createAccessGrant, fetchAccessGrants, fetchAccessRoles,
  fetchEffectiveAccessUser: vi.fn(), fetchGuardMode,
  mapAdminSystemApiError: vi.fn(() => "Ошибка"), revokeAccessGrant: vi.fn(),
  formatAccessRoleLabel: vi.fn((role) => role.label),
  fetchAccessPeople, fetchAccessPerson,
}));
vi.mock("@/lib/orgScope", () => ({ fetchDepartmentGroups: vi.fn().mockResolvedValue([]) }));
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
  it("opens with employee access view", async () => {
    render(<AccessTab />);
    expect(screen.getByRole("button", { name: "По сотрудникам" })).toHaveAttribute("aria-current", "page");
    expect(await screen.findByText("Сотрудники (0)")).toBeInTheDocument();
  });

  it("loads rights on expansion and includes revoked grants only after the switch", async () => {
    fetchAccessPeople.mockResolvedValueOnce({
      items: [{ employee_id: 20, full_name: "Тестовый сотрудник", has_current_assignment: false, position_id: null,
        position_name: null, org_unit_id: null, org_unit_name: null, org_group_id: null,
        users: [{ user_id: 7, employee_id: 20, full_name: "Тестовый сотрудник", login: "test.user",
          is_active: true, role_id: 14, role_code: "HR", role_name: "Кадры" }] }],
      unlinked_accounts: [],
    });
    render(<AccessTab />);
    fireEvent.click(await screen.findByText("Тестовый сотрудник"));
    await waitFor(() => expect(fetchAccessPerson).toHaveBeenCalledWith(7, false));
    fireEvent.click(screen.getByLabelText("Показать отозванные"));
    await waitFor(() => expect(fetchAccessPerson).toHaveBeenCalledWith(7, true));
  });

  it("shows every source in a compact table and keeps role assignment dates separate", async () => {
    fetchAccessPeople.mockResolvedValueOnce({
      items: [{ employee_id: 138, full_name: "Макибаева Акмарал Сабитовна", has_current_assignment: false,
        position_id: 86, position_name: "Руководитель отдела кадров", org_unit_id: 73,
        org_unit_name: "Отдел кадров", org_group_id: 3,
        users: [{ user_id: 361, employee_id: 138, full_name: "Макибаева Акмарал Сабитовна",
          login: "makibaeva.as", is_active: true, role_id: 14, role_code: "HR", role_name: "Кадры" }] }],
      unlinked_accounts: [],
    });
    const source = (grantId: number) => ({
      grant_id: grantId, active: true, status: "действует", source_type: "role",
      target_type: "ROLE", target_id: 14, role_name: "Кадры", role_code: "HR",
      role_assigned_at: null, grant_created_at: "2026-09-20T02:52:11Z",
      starts_at: "2026-09-20T02:52:11Z", ends_at: null,
      granted_by_user_id: 25, grantor_label: "Администратор", reason: "Тест",
      revoked_at: null, revoked_by_user_id: null, revoker_label: null, audit: [],
    });
    fetchAccessPerson.mockResolvedValueOnce({
      items: [{ code: "PERSONNEL_CARD_EDIT", label: "Редактирование личных карточек",
        section: "Личные карточки", resource_key: null, scope_type: "ORG_UNIT", scope_id: 73,
        scope_unit_name: "Отдел кадров", include_subtree: true, active: true,
        sources: [source(101), source(102)] }],
      implicit_sources: [], coverage_note: "Только выдачи", is_active: true,
    });
    render(<AccessTab />);
    fireEvent.click(await screen.findByText("Макибаева Акмарал Сабитовна"));
    const table = await screen.findByRole("table");
    for (const heading of ["Доступ", "Источник", "Область действия", "Дата выдачи"]) {
      expect(within(table).getByRole("columnheader", { name: heading })).toBeInTheDocument();
    }
    expect(within(table).getAllByText("Роль «Кадры»")).toHaveLength(2);
    expect(within(table).getAllByText("Отделение: Отдел кадров и дочерние")).toHaveLength(2);
    expect(screen.queryByText("PERSONNEL_CARD_EDIT")).not.toBeInTheDocument();
    expect(screen.queryByText("Та же роль")).not.toBeInTheDocument();
    fireEvent.click(within(table).getAllByRole("button", { name: "Редактирование личных карточек" })[0]);
    expect(within(table).getByText("PERSONNEL_CARD_EDIT")).toBeInTheDocument();
    expect(within(table).getByText("Роль назначена сотруднику: дата неизвестна")).toBeInTheDocument();
    expect(within(table).getByText("Выдал: Администратор")).toBeInTheDocument();
    expect(within(table).getByText("Причина: Тест")).toBeInTheDocument();
  });

  it("shows personnel filters only for existing USER recipients and retains generic search for other target types", async () => {
    render(<AccessTab />);
    fireEvent.click(screen.getByRole("button", { name: "Технический журнал выдач" }));
    expect(await screen.findByTestId("personnel-user-target-search")).toBeInTheDocument();
    expect(screen.queryByTestId("generic-target-search")).not.toBeInTheDocument();

    fireEvent.change(screen.getByDisplayValue("USER"), { target: { value: "EMPLOYEE" } });
    expect(screen.queryByTestId("personnel-user-target-search")).not.toBeInTheDocument();
    expect(screen.getByTestId("generic-target-search")).toBeInTheDocument();
  });

  it("uses a selected technical USER id when granting USER_ACCESS_ADMIN", async () => {
    render(<AccessTab />);
    fireEvent.click(screen.getByRole("button", { name: "Технический журнал выдач" }));
    fireEvent.click(await screen.findByTestId("personnel-user-target-search"));
    fireEvent.click(screen.getByRole("button", { name: /Создать grant/i }));

    await waitFor(() => expect(createAccessGrant).toHaveBeenCalledWith(expect.objectContaining({
      access_role_id: 1,
      target_type: "USER",
      target_id: 99,
    })));
  });
});
