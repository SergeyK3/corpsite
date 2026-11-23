import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CurrentUserProvider } from "@/lib/currentUser";
import type { MeInfo } from "@/lib/types";
import { canSeeSysadminCabinetNav, isForbiddenAdminRoute } from "@/lib/adminNav";
import DocumentationViewingBoundary from "@/components/DocumentationViewingBoundary";

const { fetchAdminUsers, createDocumentationUser } = vi.hoisted(() => ({
  fetchAdminUsers: vi.fn().mockResolvedValue([]),
  createDocumentationUser: vi.fn().mockResolvedValue({ user_id: 100, login: "guide" }),
}));
vi.mock("../../_lib/adminSystemApi.client", () => ({
  fetchAdminUsers, createDocumentationUser, forcePasswordChangeAdminUser: vi.fn(),
  lockAdminUser: vi.fn(), unlockAdminUser: vi.fn(),
  mapAdminSystemApiError: (_error: unknown, fallback: string) => fallback,
}));
import UsersTab from "./UsersTab";

afterEach(() => { cleanup(); vi.clearAllMocks(); });

const viewer: MeInfo = { role_id: 100, role_code: "DOCUMENTATION_VIEWER", is_documentation_viewer: true,
  has_sysadmin_api: false, has_personnel_admin: false, is_privileged: false };

describe("Documentation accounts", () => {
  it("defaults to a documentation profile without employee", async () => {
    render(<CurrentUserProvider value={{ role_id: 2 }}><UsersTab /></CurrentUserProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Создать аккаунт для руководства" }));
    fireEvent.change(screen.getByLabelText("Имя"), { target: { value: "Guide author" } });
    fireEvent.change(screen.getByLabelText("Логин"), { target: { value: "guide" } });
    fireEvent.change(screen.getByLabelText("Временный пароль"), { target: { value: "Temporary123" } });
    expect(screen.getByLabelText("Временный пароль")).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByRole("button", { name: /^Создать аккаунт$/ }));
    await waitFor(() => expect(createDocumentationUser).toHaveBeenCalledWith({
      full_name: "Guide author", login: "guide", temporary_password: "Temporary123",
      profile_code: "DOCUMENTATION_VIEWER",
    }));
    await waitFor(() => expect(screen.queryByLabelText("Временный пароль")).not.toBeInTheDocument());
    expect(screen.getByText(/При первом входе потребуется сменить пароль/)).toBeInTheDocument();
  });

  it("allows the system administrator to select SYSADMIN_ASSISTANT", async () => {
    render(<CurrentUserProvider value={{ role_id: 2 }}><UsersTab /></CurrentUserProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Создать аккаунт для руководства" }));
    fireEvent.change(screen.getByLabelText("Профиль"), { target: { value: "SYSADMIN_ASSISTANT" } });
    expect(screen.getByText(/применять их к реальным сотрудникам/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Имя"), { target: { value: "Assistant" } });
    fireEvent.change(screen.getByLabelText("Логин"), { target: { value: "assistant" } });
    fireEvent.change(screen.getByLabelText("Временный пароль"), { target: { value: "Temporary123" } });
    fireEvent.click(screen.getByRole("button", { name: /^Создать аккаунт$/ }));
    await waitFor(() => expect(createDocumentationUser).toHaveBeenCalledWith({full_name:"Assistant",
      login:"assistant",temporary_password:"Temporary123",profile_code:"SYSADMIN_ASSISTANT"}));
  });

  it.each([viewer, {role_id:101,is_sysadmin_assistant:true}, { role_id: 8, has_sysadmin_api: true }, { role_id: 9, has_user_access_admin: true }])(
    "does not offer standalone creation to a non-system-administrator", async me => {
      render(<CurrentUserProvider value={me}><UsersTab /></CurrentUserProvider>);
      await waitFor(() => expect(fetchAdminUsers).toHaveBeenCalled());
      expect(screen.queryByRole("button", { name: "Создать аккаунт для руководства" })).not.toBeInTheDocument();
    },
  );

  it("allows documentation navigation without write privileges", () => {
    expect(canSeeSysadminCabinetNav(viewer)).toBe(true);
    for (const path of ["/admin/system", "/admin/templates", "/directory/staff", "/directory/roles", "/directory/personnel/orders"])
      expect(isForbiddenAdminRoute(path, viewer), path).toBe(false);
    expect(viewer.has_sysadmin_api).toBe(false);
  });

  it("keeps forms and fields interactive while blocking submission and save", () => {
    const open = vi.fn(); const save = vi.fn(); const submit = vi.fn(); const preview = vi.fn();
    render(<DocumentationViewingBoundary>
      <button onClick={open}>Создать приказ</button>
      <form onSubmit={submit}><input aria-label="Название" /><button type="button" onClick={save}>Сохранить</button></form>
      <button onClick={preview}>Предпросмотр</button>
    </DocumentationViewingBoundary>);
    fireEvent.click(screen.getByText("Создать приказ"));
    fireEvent.change(screen.getByLabelText("Название"), { target: { value: "Screenshot example" } });
    fireEvent.click(screen.getByText("Сохранить"));
    fireEvent.submit(screen.getByLabelText("Название").closest("form")!);
    fireEvent.click(screen.getByText("Предпросмотр"));
    expect(open).toHaveBeenCalledOnce(); expect(preview).toHaveBeenCalledOnce();
    expect(save).not.toHaveBeenCalled(); expect(submit).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Название")).toHaveValue("Screenshot example");
  });
});
