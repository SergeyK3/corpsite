import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PersonnelApplicationRegisterDrawer from "./PersonnelApplicationRegisterDrawer";

vi.mock("@/components/OrgScopeFilter", () => ({
  default: ({
    onChange,
  }: {
    onChange: (value: { orgGroupId: number | null }) => void;
  }) => (
    <button type="button" data-testid="mock-org-scope" onClick={() => onChange({ orgGroupId: 1 })}>
      org
    </button>
  ),
}));

vi.mock("@/components/OrgUnitScopeFilter", () => ({
  default: ({
    onChange,
  }: {
    onChange: (value: { orgUnitId: number | null }) => void;
  }) => (
    <button type="button" data-testid="mock-org-unit-scope" onClick={() => onChange({ orgUnitId: 2 })}>
      unit
    </button>
  ),
}));

vi.mock("@/lib/usePersonnelOrderPositionOptions", () => ({
  usePersonnelOrderPositionOptions: () => ({
    positionGroups: [
      {
        key: "g1",
        label: "Group",
        items: [{ id: 3, label: "Position" }],
      },
    ],
    loading: false,
  }),
}));

const previewPersonnelApplicationMock = vi.fn();
const registerPersonnelApplicationMock = vi.fn();

vi.mock("../_lib/personnelApplicationsApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelApplicationsApi.client")>(
    "../_lib/personnelApplicationsApi.client",
  );
  return {
    ...actual,
    previewPersonnelApplication: (...args: unknown[]) => previewPersonnelApplicationMock(...args),
    registerPersonnelApplication: (...args: unknown[]) => registerPersonnelApplicationMock(...args),
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelApplicationRegisterDrawer", () => {
  it("runs preview flow for new person and shows registration form", async () => {
    previewPersonnelApplicationMock.mockResolvedValue({
      iin: "900101300123",
      person_exists: false,
      person_id: null,
      full_name: null,
      hr_relationship_context: null,
      has_active_employee: false,
      has_active_application: false,
      active_application_id: null,
      can_register: true,
      block_reason: null,
    });

    render(
      <PersonnelApplicationRegisterDrawer
        open
        onClose={vi.fn()}
        onRegistered={vi.fn()}
        onToast={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByTestId("register-drawer-iin-input"), {
      target: { value: "900101300123" },
    });
    fireEvent.click(screen.getByTestId("register-drawer-preview-button"));

    await waitFor(() => {
      expect(screen.getByTestId("register-drawer-form")).toBeInTheDocument();
    });
    expect(previewPersonnelApplicationMock).toHaveBeenCalledWith("900101300123");
  });

  it("blocks registration when active employee exists", async () => {
    previewPersonnelApplicationMock.mockResolvedValue({
      iin: "900101300123",
      person_exists: true,
      person_id: 5,
      full_name: "Иванов Иван",
      hr_relationship_context: "EMPLOYED",
      has_active_employee: true,
      has_active_application: false,
      active_application_id: null,
      can_register: false,
      block_reason: "ACTIVE_EMPLOYEE_BLOCKS_REGISTRATION",
    });

    render(
      <PersonnelApplicationRegisterDrawer
        open
        onClose={vi.fn()}
        onRegistered={vi.fn()}
        onToast={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByTestId("register-drawer-iin-input"), {
      target: { value: "900101300123" },
    });
    fireEvent.click(screen.getByTestId("register-drawer-preview-button"));

    await waitFor(() => {
      expect(screen.getByTestId("register-drawer-preview-error")).toHaveTextContent(/активный сотрудник/i);
    });
    expect(screen.queryByTestId("register-drawer-form")).not.toBeInTheDocument();
  });

  it("shows active application warning without registration form", async () => {
    previewPersonnelApplicationMock.mockResolvedValue({
      iin: "900101300123",
      person_exists: true,
      person_id: 5,
      full_name: "Иванов Иван",
      hr_relationship_context: "CANDIDATE",
      has_active_employee: false,
      has_active_application: true,
      active_application_id: 10,
      can_register: true,
      block_reason: null,
    });

    render(
      <PersonnelApplicationRegisterDrawer
        open
        onClose={vi.fn()}
        onRegistered={vi.fn()}
        onToast={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByTestId("register-drawer-iin-input"), {
      target: { value: "900101300123" },
    });
    fireEvent.click(screen.getByTestId("register-drawer-preview-button"));

    await waitFor(() => {
      expect(screen.getByText(/активное кадровое обращение/i)).toBeInTheDocument();
    });
    expect(screen.queryByTestId("register-drawer-form")).not.toBeInTheDocument();
  });

  it("submits successful registration", async () => {
    previewPersonnelApplicationMock.mockResolvedValue({
      iin: "900101300123",
      person_exists: false,
      person_id: null,
      full_name: null,
      hr_relationship_context: null,
      has_active_employee: false,
      has_active_application: false,
      active_application_id: null,
      can_register: true,
      block_reason: null,
    });
    registerPersonnelApplicationMock.mockResolvedValue({
      person_id: 5,
      application_id: 10,
      action: "created",
      card_href: "/directory/personnel/persons/5/card",
    });

    const onRegistered = vi.fn();
    const onClose = vi.fn();

    render(
      <PersonnelApplicationRegisterDrawer
        open
        onClose={onClose}
        onRegistered={onRegistered}
        onToast={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByTestId("register-drawer-iin-input"), {
      target: { value: "900101300123" },
    });
    fireEvent.click(screen.getByTestId("register-drawer-preview-button"));

    await waitFor(() => {
      expect(screen.getByTestId("register-drawer-form")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("register-drawer-full-name"), {
      target: { value: "Новый Претендент" },
    });
    fireEvent.click(screen.getByTestId("register-drawer-submit"));

    await waitFor(() => {
      expect(registerPersonnelApplicationMock).toHaveBeenCalled();
      expect(onRegistered).toHaveBeenCalledWith(
        expect.objectContaining({ application_id: 10, card_href: "/directory/personnel/persons/5/card" }),
      );
      expect(onClose).toHaveBeenCalled();
    });
  });
});
