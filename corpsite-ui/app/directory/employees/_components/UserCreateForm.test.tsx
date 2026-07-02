import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import UserCreateForm from "./UserCreateForm";

describe("UserCreateForm login field", () => {
  afterEach(() => {
    cleanup();
  });

  it("prefills suggested login and remains editable before submit", () => {
    const onSubmit = vi.fn();

    render(
      <UserCreateForm
        fullName="Козгамбаева Ляззат Таласпаевна"
        orgUnitLabel="Отделение"
        initialValues={{
          login: "kozgambaeva.lt",
          password: "TempPass123!",
          role_id: "5",
          is_active: true,
        }}
        roleOptions={[{ id: 5, label: "QM role" }]}
        onCancel={() => {}}
        onSubmit={onSubmit}
      />,
    );

    const loginInput = screen.getByLabelText(/Логин/i) as HTMLInputElement;
    expect(loginInput.value).toBe("kozgambaeva.lt");
    expect(loginInput).not.toHaveAttribute("readonly");

    fireEvent.change(loginInput, { target: { value: "custom.login" } });
    expect(loginInput.value).toBe("custom.login");

    fireEvent.submit(screen.getByRole("button", { name: "Создать" }).closest("form")!);
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ login: "custom.login" }),
    );
  });
});
