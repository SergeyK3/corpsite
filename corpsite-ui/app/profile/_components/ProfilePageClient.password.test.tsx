import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ProfilePageClient from "./ProfilePageClient";
import { apiAuthMe } from "@/lib/api";
import { logout } from "@/lib/auth";

const replace = vi.fn();

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("@/lib/auth", () => ({ isAuthed: () => true, logout: vi.fn() }));
vi.mock("@/lib/api", () => ({ apiAuthMe: vi.fn() }));
vi.mock("@/components/TelegramBindPanel", () => ({ default: () => null }));
vi.mock("./PasswordChangePanel", () => ({
  default: ({ onSuccess }: { onSuccess: () => void }) => (
    <button type="button" onClick={onSuccess}>password-change-success</button>
  ),
}));

afterEach(() => vi.clearAllMocks());

describe("ProfilePageClient password completion", () => {
  it("clears the session and redirects to login after a successful password change", async () => {
    vi.mocked(apiAuthMe).mockResolvedValue({ user_id: 1, login: "employee" });
    render(<ProfilePageClient />);

    await waitFor(() => expect(apiAuthMe).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "password-change-success" }));

    expect(logout).toHaveBeenCalledOnce();
    expect(replace).toHaveBeenCalledWith("/login");
  });
});
