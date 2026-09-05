import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
  it("renders one capability-gated management link in page content and none in the global sidebar", async () => {
    render(
      <AppShell>
        <SystemAdminPage />
      </AppShell>,
    );

    const links = await screen.findAllByRole("link", { name: /Управление тестовыми данными персонала/ });
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute("href", "/admin/system/test-personnel-data");
    expect(links[0].closest("aside")).toBeNull();
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

    await waitFor(() => expect(screen.queryByText("Загрузка…")).not.toBeInTheDocument());
    expect(screen.queryAllByRole("link", { name: /Управление тестовыми данными персонала/ })).toHaveLength(0);
  });
});
