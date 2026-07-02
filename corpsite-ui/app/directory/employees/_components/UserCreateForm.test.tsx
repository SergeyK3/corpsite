import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import UserCreateForm from "./UserCreateForm";

vi.mock("@/components/OrgScopeFilter", () => ({
  default: ({
    label,
    value,
    onChange,
  }: {
    label: string;
    value?: number | null;
    onChange?: (groupId: number | null) => void;
  }) => (
    <div>
      <label htmlFor="mock-org-group">{label}</label>
      <select
        id="mock-org-group"
        value={value != null ? String(value) : ""}
        onChange={(e) => onChange?.(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">Все</option>
        <option value="1">Group 1</option>
        <option value="2">Group 2</option>
      </select>
    </div>
  ),
}));

vi.mock("@/components/OrgUnitScopeFilter", () => ({
  default: ({
    label,
    orgGroupId,
    value,
    onChange,
  }: {
    label: string;
    orgGroupId?: number | null;
    value?: number | null;
    onChange?: (unitId: number | null) => void;
  }) => (
    <div>
      <label htmlFor="mock-org-unit">{label}</label>
      <select
        id="mock-org-unit"
        data-group-id={orgGroupId ?? ""}
        value={value != null ? String(value) : ""}
        onChange={(e) => onChange?.(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">Выберите отделение</option>
        {orgGroupId === 1 ? (
          <>
            <option value="44">Ambulatory</option>
            <option value="45">Hospital</option>
          </>
        ) : null}
        {orgGroupId === 2 ? <option value="20">Group B unit</option> : null}
      </select>
    </div>
  ),
}));

vi.mock("@/lib/platformRoleCatalog", () => ({
  listPlatformRoleCatalog: vi.fn().mockResolvedValue([
    { id: 5, label: "QM Head", code: "QM_HEAD" },
    { id: 99, label: "Unused Role", code: "UNUSED_ROLE" },
  ]),
}));

const KOZGAMBAEVA_FIO = "Козгамбаева Ляззат Таласпаевна";

const baseInitialValues = {
  login: "",
  password: "",
  role_id: "",
  org_unit_id: "",
  is_active: true,
};

describe("UserCreateForm login field", () => {
  afterEach(() => {
    cleanup();
  });

  it("suggests kozgambaeva.lt for three-part FIO on mount", async () => {
    render(
      <UserCreateForm
        fullName={KOZGAMBAEVA_FIO}
        initialOrgGroupId={1}
        initialOrgUnitId={44}
        initialValues={baseInitialValues}
        onCancel={() => {}}
        onSubmit={() => {}}
      />,
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Логин/i)).toHaveValue("kozgambaeva.lt");
    });
    expect(screen.getByText(/Аккаунт для:/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/^ФИО$/i)).not.toBeInTheDocument();
  });

  it("overrides legacy talaspaevnak seed with OPS-028 policy", async () => {
    render(
      <UserCreateForm
        fullName={KOZGAMBAEVA_FIO}
        initialOrgGroupId={1}
        initialOrgUnitId={44}
        initialValues={{ ...baseInitialValues, login: "talaspaevnak" }}
        onCancel={() => {}}
        onSubmit={() => {}}
      />,
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Логин/i)).toHaveValue("kozgambaeva.lt");
    });
  });

  it("keeps policy login when fullName temporarily becomes placeholder", async () => {
    const { rerender } = render(
      <UserCreateForm
        fullName={KOZGAMBAEVA_FIO}
        initialOrgGroupId={1}
        initialOrgUnitId={44}
        initialValues={{ ...baseInitialValues, login: "talaspaevnak" }}
        onCancel={() => {}}
        onSubmit={() => {}}
      />,
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Логин/i)).toHaveValue("kozgambaeva.lt");
    });

    rerender(
      <UserCreateForm
        fullName="—"
        initialOrgGroupId={1}
        initialOrgUnitId={44}
        initialValues={{ ...baseInitialValues, login: "talaspaevnak" }}
        onCancel={() => {}}
        onSubmit={() => {}}
      />,
    );

    expect(screen.getByLabelText(/Логин/i)).toHaveValue("kozgambaeva.lt");
  });

  it("prefills org scope and filters units by selected group", async () => {
    render(
      <UserCreateForm
        fullName={KOZGAMBAEVA_FIO}
        initialOrgGroupId={1}
        initialOrgUnitId={44}
        initialValues={baseInitialValues}
        onCancel={() => {}}
        onSubmit={() => {}}
      />,
    );

    const unitSelect = screen.getByLabelText(/Отделение/i) as HTMLSelectElement;
    expect(unitSelect.value).toBe("44");
    expect(unitSelect.getAttribute("data-group-id")).toBe("1");

    fireEvent.change(screen.getByLabelText(/Группа отделений/i), { target: { value: "2" } });
    expect((screen.getByLabelText(/Отделение/i) as HTMLSelectElement).getAttribute("data-group-id")).toBe("2");
  });

  it("loads Platform Role catalog including unused roles", async () => {
    render(
      <UserCreateForm
        fullName={KOZGAMBAEVA_FIO}
        initialOrgGroupId={1}
        initialOrgUnitId={44}
        initialValues={baseInitialValues}
        onCancel={() => {}}
        onSubmit={() => {}}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole("option", { name: /UNUSED_ROLE/i })).toBeInTheDocument();
    });
    expect(screen.getByLabelText(/Роль Corpsite/i)).toBeInTheDocument();
  });

  it("prefills suggested login and remains editable before submit", async () => {
    const onSubmit = vi.fn();

    render(
      <UserCreateForm
        fullName={KOZGAMBAEVA_FIO}
        initialOrgGroupId={1}
        initialOrgUnitId={44}
        initialValues={{
          ...baseInitialValues,
          login: "kozgambaeva.lt",
          password: "TempPass123!",
          role_id: "5",
        }}
        onCancel={() => {}}
        onSubmit={onSubmit}
      />,
    );

    await waitFor(() => {
      expect(screen.getByLabelText(/Логин/i)).toHaveValue("kozgambaeva.lt");
    });

    const loginInput = screen.getByLabelText(/Логин/i) as HTMLInputElement;
    fireEvent.change(loginInput, { target: { value: "custom.login" } });
    expect(loginInput.value).toBe("custom.login");

    fireEvent.submit(screen.getByRole("button", { name: "Создать" }).closest("form")!);
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ login: "custom.login", org_unit_id: "44" }),
    );
  });
});
