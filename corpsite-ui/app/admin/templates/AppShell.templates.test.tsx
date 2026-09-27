import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AppShell from "@/components/AppShell";
import { apiAuthMe } from "@/lib/api";

const replace = vi.fn();
const push = vi.fn();

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/templates",
  useRouter: () => ({ replace, push }),
}));
vi.mock("@/lib/auth", () => ({
  isAuthed: () => true,
  logout: vi.fn(),
}));
vi.mock("@/lib/api", () => ({ apiAuthMe: vi.fn() }));

describe("AppShell templates navigation", () => {
  beforeEach(() => {
    replace.mockReset();
    push.mockReset();
    vi.mocked(apiAuthMe).mockReset().mockResolvedValue({
      user_id: 2,
      role_id: 2,
      role_code: "ADMIN",
      is_system_admin: true,
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows one Templates sidebar item that points to the canonical route", async () => {
    render(
      <AppShell>
        <div>Содержимое страницы</div>
      </AppShell>,
    );

    const templatesLink = await screen.findByRole("link", { name: "Шаблоны" });
    expect(templatesLink).toHaveAttribute("href", "/admin/templates");
    expect(screen.queryByRole("link", { name: "Шаблоны регулярных задач" })).not.toBeInTheDocument();
  });
});
