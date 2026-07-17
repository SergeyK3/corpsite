import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelApplicationRegisterDrawer from "./PersonnelApplicationRegisterDrawer";

const UNIT_2_POSITIONS = [
  { id: 10, label: "Медсестра (отделение 2)" },
  { id: 11, label: "Врач (отделение 2)" },
];

const UNIT_3_POSITIONS = [{ id: 20, label: "Лаборант (отделение 3)" }];

const GLOBAL_ONLY_POSITION = { id: 99, label: "Должность другого отделения" };

const usePersonnelOrderPositionOptionsMock = vi.fn();

vi.mock("@/components/OrgScopeFilter", () => ({
  default: ({ onChange }: { onChange: (groupId: number | null) => void }) => (
    <button type="button" data-testid="mock-org-scope" onClick={() => onChange(1)}>
      org group
    </button>
  ),
}));

vi.mock("@/components/OrgUnitScopeFilter", () => ({
  default: ({
    onChange,
    disabled,
    value,
  }: {
    onChange: (unitId: number | null) => void;
    disabled?: boolean;
    value?: number | null;
  }) => (
    <div data-testid="mock-org-unit-scope">
      <button
        type="button"
        data-testid="mock-org-unit-2"
        disabled={disabled}
        aria-pressed={value === 2}
        onClick={() => onChange(2)}
      >
        Unit 2
      </button>
      <button
        type="button"
        data-testid="mock-org-unit-3"
        disabled={disabled}
        aria-pressed={value === 3}
        onClick={() => onChange(3)}
      >
        Unit 3
      </button>
    </div>
  ),
}));

vi.mock("@/lib/useOrgUnitScopeOptions", () => ({
  useOrgUnitScopeOptions: () => ({
    options: [
      { unit_id: 2, group_id: 1, name: "Unit 2" },
      { unit_id: 3, group_id: 1, name: "Unit 3" },
    ],
    catalogOptions: [
      { unit_id: 2, group_id: 1, name: "Unit 2" },
      { unit_id: 3, group_id: 1, name: "Unit 3" },
    ],
    loading: false,
    error: null,
  }),
}));

vi.mock("@/lib/usePersonnelOrderPositionOptions", () => ({
  usePersonnelOrderPositionOptions: (...args: unknown[]) => usePersonnelOrderPositionOptionsMock(...args),
}));

const previewPersonnelApplicationMock = vi.fn();
const registerPersonnelApplicationMock = vi.fn();
const issueIntakeLinkMock = vi.fn();

vi.mock("../_lib/personnelApplicationsApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelApplicationsApi.client")>(
    "../_lib/personnelApplicationsApi.client",
  );
  return {
    ...actual,
    previewPersonnelApplication: (...args: unknown[]) => previewPersonnelApplicationMock(...args),
    registerPersonnelApplication: (...args: unknown[]) => registerPersonnelApplicationMock(...args),
    issueIntakeLink: (...args: unknown[]) => issueIntakeLinkMock(...args),
  };
});

function mockPositionsForUnit(orgUnitId: number | null) {
  if (orgUnitId === 2) {
    return {
      scopedOptions: UNIT_2_POSITIONS,
      loading: false,
    };
  }
  if (orgUnitId === 3) {
    return {
      scopedOptions: UNIT_3_POSITIONS,
      loading: false,
    };
  }
  return {
    scopedOptions: [],
    loading: false,
  };
}

function setupPositionOptionsMock() {
  usePersonnelOrderPositionOptionsMock.mockImplementation(
    ({ orgUnitId }: { orgUnitId: number | null; allowedOnly?: boolean }) => {
      const { scopedOptions, loading } = mockPositionsForUnit(orgUnitId);
      return {
        scopedOptions,
        loading,
      };
    },
  );
}

async function openRegistrationForm(options?: { selectOrgGroup?: boolean }) {
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
  if (options?.selectOrgGroup !== false) {
    fireEvent.click(screen.getByTestId("mock-org-scope"));
  }
}

function positionSelectOptions() {
  return within(screen.getByTestId("register-drawer-position")).getAllByRole("option");
}

beforeEach(() => {
  setupPositionOptionsMock();
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
  issueIntakeLinkMock.mockResolvedValue({
    application_id: 10,
    link_id: 1,
    intake_url_path: "/intake/abc123",
    expires_at: "2026-08-01T00:00:00Z",
    status: "issued",
    reissued: false,
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("PersonnelApplicationRegisterDrawer", () => {
  it("runs preview flow for new person and shows registration form with placement cascade", async () => {
    render(
      <PersonnelApplicationRegisterDrawer
        open
        onClose={vi.fn()}
        onRegistered={vi.fn()}
        onToast={vi.fn()}
      />,
    );

    await openRegistrationForm({ selectOrgGroup: false });

    expect(previewPersonnelApplicationMock).toHaveBeenCalledWith("900101300123");
    expect(screen.getByTestId("register-drawer-intended-placement")).toBeInTheDocument();
    expect(screen.getByTestId("mock-org-unit-2")).toBeDisabled();
    expect(screen.getByTestId("register-drawer-position")).toBeDisabled();
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
});

describe("PersonnelApplicationRegisterDrawer placement cascade", () => {
  it("shows only allowed positions for the selected org unit", async () => {
    render(
      <PersonnelApplicationRegisterDrawer
        open
        onClose={vi.fn()}
        onRegistered={vi.fn()}
        onToast={vi.fn()}
      />,
    );

    await openRegistrationForm();
    fireEvent.click(screen.getByTestId("mock-org-unit-2"));

    await waitFor(() => {
      expect(screen.getByTestId("register-drawer-position")).not.toBeDisabled();
    });

    const labels = positionSelectOptions().map((option) => option.textContent);
    expect(labels).toContain("Медсестра (отделение 2)");
    expect(labels).toContain("Врач (отделение 2)");
    expect(labels).not.toContain(GLOBAL_ONLY_POSITION.label);
    expect(usePersonnelOrderPositionOptionsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        orgUnitId: 2,
        orgGroupId: 1,
        allowedOnly: true,
      }),
    );
  });

  it("clears position when org unit changes", async () => {
    render(
      <PersonnelApplicationRegisterDrawer
        open
        onClose={vi.fn()}
        onRegistered={vi.fn()}
        onToast={vi.fn()}
      />,
    );

    await openRegistrationForm();
    fireEvent.click(screen.getByTestId("mock-org-unit-2"));
    fireEvent.change(screen.getByTestId("register-drawer-position"), {
      target: { value: "10" },
    });
    expect(screen.getByTestId("register-drawer-position")).toHaveValue("10");

    fireEvent.click(screen.getByTestId("mock-org-unit-3"));

    await waitFor(() => {
      expect(screen.getByTestId("register-drawer-position")).toHaveValue("");
    });
    expect(positionSelectOptions().map((option) => option.textContent)).toContain("Лаборант (отделение 3)");
  });

  it("submits allowed position and continues register to issueIntakeLink", async () => {
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

    await openRegistrationForm();
    fireEvent.click(screen.getByTestId("mock-org-unit-2"));
    fireEvent.change(screen.getByTestId("register-drawer-position"), {
      target: { value: "10" },
    });

    await waitFor(() => {
      expect(screen.getByTestId("register-drawer-submit")).not.toBeDisabled();
    });
    fireEvent.click(screen.getByTestId("register-drawer-submit"));

    await waitFor(() => {
      expect(registerPersonnelApplicationMock).toHaveBeenCalledWith(
        expect.objectContaining({
          intended_org_group_id: 1,
          intended_org_unit_id: 2,
          intended_position_id: 10,
        }),
      );
      expect(issueIntakeLinkMock).toHaveBeenCalledWith(10);
      expect(onRegistered).toHaveBeenCalled();
    });

    expect(await screen.findByTestId("register-drawer-success")).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("rejects position that is not allowed for the selected org unit", async () => {
    const onToast = vi.fn();

    render(
      <PersonnelApplicationRegisterDrawer
        open
        onClose={vi.fn()}
        onRegistered={vi.fn()}
        onToast={onToast}
      />,
    );

    await openRegistrationForm();
    fireEvent.click(screen.getByTestId("mock-org-unit-2"));
    fireEvent.change(screen.getByTestId("register-drawer-position"), {
      target: { value: String(GLOBAL_ONLY_POSITION.id) },
    });

    await waitFor(() => {
      expect(screen.getByTestId("register-drawer-submit")).toBeDisabled();
    });

    fireEvent.click(screen.getByTestId("register-drawer-submit"));

    expect(registerPersonnelApplicationMock).not.toHaveBeenCalled();
    expect(issueIntakeLinkMock).not.toHaveBeenCalled();
    expect(onToast).not.toHaveBeenCalled();
  });

  it("shows empty-state message when unit has no allowed positions", async () => {
    usePersonnelOrderPositionOptionsMock.mockImplementation(() => ({
      scopedOptions: [],
      loading: false,
    }));

    render(
      <PersonnelApplicationRegisterDrawer
        open
        onClose={vi.fn()}
        onRegistered={vi.fn()}
        onToast={vi.fn()}
      />,
    );

    await openRegistrationForm();
    fireEvent.click(screen.getByTestId("mock-org-unit-2"));

    await waitFor(() => {
      expect(screen.getByTestId("register-drawer-position-empty")).toBeInTheDocument();
    });
    expect(screen.getByTestId("register-drawer-submit")).toBeDisabled();
  });
});
