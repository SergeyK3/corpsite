import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import LoginPage from "./page";

const apiFetchJson = vi.fn();
vi.mock("@/lib/api", () => ({ apiAuthLogin: vi.fn(), apiAuthMe: vi.fn(), apiFetchJson: (...args: unknown[]) => apiFetchJson(...args) }));
vi.mock("@/lib/auth", () => ({ isAuthed: () => false, logout: vi.fn(), setSessionLogin: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

describe("LoginPage Telegram recovery", () => {
  it("uses the same login form to request and complete a Telegram recovery", async () => {
    apiFetchJson.mockResolvedValueOnce({ message: "Если для этой учётной записи доступно восстановление, код отправлен в Telegram." });
    apiFetchJson.mockResolvedValueOnce({ message: "Пароль изменён. Выполните вход с новым паролем." });
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText("Логин"), { target: { value: "staff.login" } });
    fireEvent.click(screen.getByRole("button", { name: "Забыли пароль?" }));
    fireEvent.click(screen.getByRole("button", { name: "Отправить код в Telegram" }));
    await waitFor(() => expect(apiFetchJson).toHaveBeenCalledWith("/auth/password-recovery/telegram/request", expect.anything()));
    fireEvent.change(screen.getByLabelText("Код из Telegram"), { target: { value: "12345678" } });
    fireEvent.change(screen.getByLabelText("Новый пароль для восстановления"), { target: { value: "new-password" } });
    fireEvent.change(screen.getByLabelText("Подтвердите новый пароль"), { target: { value: "new-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Установить новый пароль" }));
    await waitFor(() => expect(apiFetchJson).toHaveBeenLastCalledWith("/auth/password-recovery/telegram/complete", expect.anything()));
  });
});
