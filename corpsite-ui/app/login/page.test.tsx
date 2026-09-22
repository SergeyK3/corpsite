import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "./page";

const apiFetchJson = vi.fn();
vi.mock("@/lib/api", () => ({ apiAuthLogin: vi.fn(), apiAuthMe: vi.fn(), apiFetchJson: (...args: unknown[]) => apiFetchJson(...args) }));
vi.mock("@/lib/auth", () => ({ isAuthed: () => false, logout: vi.fn(), setSessionLogin: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

describe("LoginPage Telegram recovery", () => {
  afterEach(cleanup);

  beforeEach(() => {
    apiFetchJson.mockReset();
  });

  it("uses the same login form to request and complete a Telegram recovery", async () => {
    apiFetchJson.mockResolvedValueOnce({ message: "Если для этой учётной записи доступно восстановление, код отправлен в Telegram." });
    apiFetchJson.mockResolvedValueOnce({ message: "Пароль изменён. Выполните вход с новым паролем." });
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText("Логин"), { target: { value: "staff.login" } });
    fireEvent.click(screen.getByRole("button", { name: "Забыли пароль?" }));
    expect(screen.queryByLabelText("Код из Telegram")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Получить код в Telegram" }));
    await waitFor(() => expect(apiFetchJson).toHaveBeenNthCalledWith(1, "/auth/password-recovery/telegram/request", {
      method: "POST",
      body: { login: "staff.login" },
      noAuth: true,
    }));
    expect(await screen.findByRole("status")).toHaveTextContent("Запрос принят. Если Telegram привязан к этой учётной записи, код придёт в Telegram. Проверьте телефон.");
    expect(screen.getByLabelText("Код из Telegram")).toBeVisible();
    expect(screen.getByLabelText("Новый пароль")).toBeVisible();
    expect(screen.getByLabelText("Подтверждение нового пароля")).toBeVisible();
    expect(screen.getByRole("button", { name: "Установить новый пароль" })).toBeVisible();
    expect(screen.getByLabelText("Код из Telegram")).toHaveAttribute("name", "telegram-recovery-code");
    expect(screen.getByLabelText("Код из Telegram")).toHaveAttribute("autocomplete", "one-time-code");
    expect(screen.getByLabelText("Новый пароль")).toHaveAttribute("name", "telegram-recovery-password");
    expect(screen.getByLabelText("Новый пароль")).toHaveAttribute("autocomplete", "new-password");
    expect(screen.getByLabelText("Подтверждение нового пароля")).toHaveAttribute("name", "telegram-recovery-confirmation");
    expect(screen.getByLabelText("Подтверждение нового пароля")).toHaveAttribute("autocomplete", "new-password");
    fireEvent.click(screen.getByRole("button", { name: "Показать новый пароль" }));
    expect(screen.getByLabelText("Новый пароль")).toHaveAttribute("type", "text");
    expect(screen.getByLabelText("Подтверждение нового пароля")).toHaveAttribute("type", "password");
    fireEvent.click(screen.getByRole("button", { name: "Показать подтверждение нового пароля" }));
    expect(screen.getByLabelText("Подтверждение нового пароля")).toHaveAttribute("type", "text");
    fireEvent.change(screen.getByLabelText("Код из Telegram"), { target: { value: "12345678" } });
    fireEvent.change(screen.getByLabelText("Новый пароль"), { target: { value: "new-password" } });
    fireEvent.change(screen.getByLabelText("Подтверждение нового пароля"), { target: { value: "new-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Установить новый пароль" }));
    await waitFor(() => expect(apiFetchJson).toHaveBeenLastCalledWith("/auth/password-recovery/telegram/complete", {
      method: "POST",
      body: {
        login: "staff.login",
        code: "12345678",
        new_password: "new-password",
        new_password_confirmation: "new-password",
      },
      noAuth: true,
    }));
  });

  it("shows a technical error instead of claiming that a code was sent", async () => {
    apiFetchJson.mockRejectedValueOnce(new Error("network unavailable"));
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText("Логин"), { target: { value: "staff.login" } });
    fireEvent.click(screen.getByRole("button", { name: "Забыли пароль?" }));
    fireEvent.click(screen.getByRole("button", { name: "Получить код в Telegram" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Не удалось связаться с сервером. Повторите попытку позже");
    expect(screen.queryByText(/код отправлен/i)).not.toBeInTheDocument();
  });
});
