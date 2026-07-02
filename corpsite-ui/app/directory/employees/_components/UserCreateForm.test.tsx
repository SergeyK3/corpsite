import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import UserCreateForm from "./UserCreateForm";

const KOZGAMBAEVA_FIO = "Козгамбаева Ляззат Таласпаевна";

describe("UserCreateForm login field", () => {
  afterEach(() => {
    cleanup();
  });

  it("suggests kozgambaeva.lt for three-part FIO on mount", () => {
    render(
      <UserCreateForm
        fullName={KOZGAMBAEVA_FIO}
        orgUnitLabel="Отделение"
        initialValues={{
          login: "",
          password: "",
          role_id: "",
          is_active: true,
        }}
        roleOptions={[]}
        onCancel={() => {}}
        onSubmit={() => {}}
      />,
    );

    expect(screen.getByLabelText(/Логин/i)).toHaveValue("kozgambaeva.lt");
  });

  it("overrides legacy talaspaevnak seed with OPS-028 policy", () => {
    render(
      <UserCreateForm
        fullName={KOZGAMBAEVA_FIO}
        orgUnitLabel="Отделение"
        initialValues={{
          login: "talaspaevnak",
          password: "",
          role_id: "",
          is_active: true,
        }}
        roleOptions={[]}
        onCancel={() => {}}
        onSubmit={() => {}}
      />,
    );

    expect(screen.getByLabelText(/Логин/i)).toHaveValue("kozgambaeva.lt");
  });

  it("keeps policy login when fullName temporarily becomes placeholder", () => {
    const { rerender } = render(
      <UserCreateForm
        fullName={KOZGAMBAEVA_FIO}
        orgUnitLabel="Отделение"
        initialValues={{
          login: "talaspaevnak",
          password: "",
          role_id: "",
          is_active: true,
        }}
        roleOptions={[]}
        onCancel={() => {}}
        onSubmit={() => {}}
      />,
    );

    expect(screen.getByLabelText(/Логин/i)).toHaveValue("kozgambaeva.lt");

    rerender(
      <UserCreateForm
        fullName="—"
        orgUnitLabel="Отделение"
        initialValues={{
          login: "talaspaevnak",
          password: "",
          role_id: "",
          is_active: true,
        }}
        roleOptions={[]}
        onCancel={() => {}}
        onSubmit={() => {}}
      />,
    );

    expect(screen.getByLabelText(/Логин/i)).toHaveValue("kozgambaeva.lt");
    expect(screen.getByLabelText(/Логин/i)).not.toHaveValue("talaspaevnak");
  });

  it("prefills suggested login and remains editable before submit", () => {
    const onSubmit = vi.fn();

    render(
      <UserCreateForm
        fullName="Козgамbaева Лязzат Тalасpaevna"
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
