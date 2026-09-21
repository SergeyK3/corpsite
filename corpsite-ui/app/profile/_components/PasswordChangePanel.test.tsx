import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PasswordChangePanel from "./PasswordChangePanel";
import { apiAuthPasswordChange } from "@/lib/api";

vi.mock("@/lib/api", () => ({ apiAuthPasswordChange: vi.fn() }));

const changePassword = vi.mocked(apiAuthPasswordChange);

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function fillPasswords(current: string, next: string, confirmation: string) {
  fireEvent.change(screen.getByLabelText("Текущий пароль"), { target: { value: current } });
  fireEvent.change(screen.getByLabelText("Новый пароль", { exact: true }), { target: { value: next } });
  fireEvent.change(screen.getByLabelText("Подтверждение нового пароля"), { target: { value: confirmation } });
}

describe("PasswordChangePanel", () => {
  it("toggles each password field locally without clearing its value or calling the API", () => {
    render(<PasswordChangePanel onSuccess={vi.fn()} />);
    fillPasswords("CurrentPass123", "NewPass123", "ConfirmPass123");

    const fields = [
      ["Текущий пароль", "Показать текущий пароль", "CurrentPass123"],
      ["Новый пароль", "Показать новый пароль", "NewPass123"],
      ["Подтверждение нового пароля", "Показать подтверждение нового пароля", "ConfirmPass123"],
    ] as const;
    for (const [label, showLabel, value] of fields) {
      const input = screen.getByLabelText(label, { exact: true });
      expect(input).toHaveAttribute("type", "password");
      fireEvent.click(screen.getByRole("button", { name: showLabel }));
      expect(input).toHaveAttribute("type", "text");
      expect(input).toHaveValue(value);
      fireEvent.click(screen.getByRole("button", { name: showLabel.replace("Показать", "Скрыть") }));
      expect(input).toHaveAttribute("type", "password");
      expect(input).toHaveValue(value);
    }
    expect(changePassword).not.toHaveBeenCalled();
  });

  it("sends only password fields and finishes the session after success", async () => {
    changePassword.mockResolvedValue({ message: "ok" });
    const onSuccess = vi.fn();
    render(<PasswordChangePanel onSuccess={onSuccess} />);

    fillPasswords("CurrentPass123", "NewPass123", "NewPass123");
    fireEvent.click(screen.getByRole("button", { name: "Изменить пароль" }));

    await waitFor(() => expect(changePassword).toHaveBeenCalledWith({
      current_password: "CurrentPass123",
      new_password: "NewPass123",
      new_password_confirmation: "NewPass123",
    }));
    expect(onSuccess).toHaveBeenCalledOnce();
  });

  it("does not submit when confirmation differs", () => {
    render(<PasswordChangePanel onSuccess={vi.fn()} />);
    fillPasswords("CurrentPass123", "NewPass123", "OtherPass123");
    fireEvent.click(screen.getByRole("button", { name: "Изменить пароль" }));

    expect(changePassword).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Подтверждение нового пароля не совпадает.");
  });
});
