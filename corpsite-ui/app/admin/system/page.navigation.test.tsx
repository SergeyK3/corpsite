import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SystemAdminPage from "./page";
import AppShell from "@/components/AppShell";
import { apiAuthMe } from "@/lib/api";

const replace = vi.fn();
const push = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/system",
  useRouter: () => ({ replace, push }),
}));
vi.mock("@/lib/auth", () => ({
  isAuthed: () => true,
  logout: vi.fn(),
}));
vi.mock("@/lib/api", () => ({ apiAuthMe: vi.fn() }));
vi.mock("./_components/TelegramStatusPanel", () => ({ default: () => null }));
vi.mock("./_components/tabs/AccessTab", () => ({ default: () => null }));
vi.mock("./_components/tabs/AssignmentsTab", () => ({ default: () => null }));
vi.mock("./_components/tabs/AuditTab", () => ({ default: () => null }));
vi.mock("./_components/tabs/EnrollmentTab", () => ({ default: () => null }));
vi.mock("./_components/tabs/UserLinkageReviewTab", () => ({ default: () => null }));
vi.mock("./_components/tabs/UsersTab", () => ({ default: () => null }));
vi.mock("./_components/tabs/VisibilityTab", () => ({ default: () => null }));

beforeEach(() => {
  replace.mockReset();
  push.mockReset();
  vi.mocked(apiAuthMe).mockReset().mockResolvedValue({
    user_id: 25,
    role_id: 2,
    role_code: "ADMIN",
    is_system_admin: true,
    has_sysadmin_api: true,
    can_request_test_personnel_deletion: true,
  });
});

afterEach(cleanup);

describe("system admin page navigation", () => {
  it("renders lifecycle and capability-gated test personnel links in the section row", async () => {
    render(
      <AppShell>
        <SystemAdminPage />
      </AppShell>,
    );

    const sections = await screen.findByRole("navigation", { name: "Разделы кабинета" });
    const lifecycle = within(sections).getByRole("link", { name: "Жизненный цикл" });
    const testPersonnel = within(sections).getByRole("link", { name: "Тестовые данные" });
    expect(lifecycle).toHaveAttribute("href", "/admin/system/personnel-lifecycle");
    expect(testPersonnel).toHaveAttribute("href", "/admin/system/test-personnel-data");
    expect(lifecycle.closest("nav")).toHaveAttribute("aria-label", "Разделы кабинета");
    expect(testPersonnel.closest("nav")).toBe(lifecycle.closest("nav"));
    expect(screen.queryByText("Жизненный цикл персонала →")).not.toBeInTheDocument();
    expect(screen.queryByText("Управление тестовыми данными персонала →")).not.toBeInTheDocument();
    expect(sections).toHaveClass("flex-wrap", "xl:flex-nowrap");
    expect(lifecycle).toHaveClass("whitespace-nowrap");
    expect(testPersonnel).toHaveClass("whitespace-nowrap");

    const activeSection = within(sections).getByRole("button", { name: "Пользователи" });
    expect(activeSection).toHaveAttribute("aria-current", "page");
    expect(activeSection).toHaveClass("border-blue-900", "font-semibold", "ring-2");
  });

  it("renders no management link without the request capability", async () => {
    vi.mocked(apiAuthMe).mockResolvedValue({
      user_id: 25,
      role_id: 2,
      role_code: "ADMIN",
      is_system_admin: true,
      has_sysadmin_api: true,
      can_request_test_personnel_deletion: false,
    });

    render(
      <AppShell>
        <SystemAdminPage />
      </AppShell>,
    );

    const sections = await screen.findByRole("navigation", { name: "Разделы кабинета" });
    expect(within(sections).queryByRole("link", { name: "Тестовые данные" })).not.toBeInTheDocument();
    expect(within(sections).getByRole("link", { name: "Жизненный цикл" })).toHaveAttribute(
      "href",
      "/admin/system/personnel-lifecycle",
    );
  });
});
