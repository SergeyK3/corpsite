import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const navigation = vi.hoisted(() => ({
  pathname: "/intake/valid-token",
  replace: vi.fn(),
  push: vi.fn(),
}));
const auth = vi.hoisted(() => ({ isAuthed: vi.fn(() => false), logout: vi.fn() }));
const api = vi.hoisted(() => ({ apiAuthMe: vi.fn() }));

vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
  useRouter: () => ({ replace: navigation.replace, push: navigation.push }),
}));
vi.mock("next/link", () => ({ default: ({ children }: { children: React.ReactNode }) => <>{children}</> }));
vi.mock("@/lib/auth", () => auth);
vi.mock("@/lib/api", () => api);
vi.mock("@/lib/currentUser", () => ({
  CurrentUserProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import AppShell from "@/components/AppShell";

describe("AppShell public intake access", () => {
  afterEach(() => {
    cleanup();
    navigation.replace.mockClear();
    navigation.push.mockClear();
    auth.isAuthed.mockClear();
    auth.logout.mockClear();
    api.apiAuthMe.mockClear();
    navigation.pathname = "/intake/valid-token";
  });

  it("opens a tokenized intake route without authentication or a login redirect", () => {
    render(
      <AppShell>
        <div>Анкета претендента</div>
      </AppShell>,
    );

    expect(screen.getByText("Анкета претендента")).toBeInTheDocument();
    expect(auth.isAuthed).not.toHaveBeenCalled();
    expect(api.apiAuthMe).not.toHaveBeenCalled();
    expect(navigation.replace).not.toHaveBeenCalled();
  });

  it.each(["/directory/staff", "/admin/system"])("keeps %s behind login", async (pathname) => {
    navigation.pathname = pathname;
    render(
      <AppShell>
        <div>Защищённый раздел</div>
      </AppShell>,
    );

    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/login"));
    expect(auth.isAuthed).toHaveBeenCalled();
  });
});
