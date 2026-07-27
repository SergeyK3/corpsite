import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelLkPageClient from "./PersonnelLkPageClient";
import type { PersonnelLkRegistryItem } from "../_lib/personnelLkApi.client";
import { CurrentUserProvider } from "@/lib/currentUser";
import type { MeInfo } from "@/lib/types";

const replaceMock = vi.fn();
let currentSearchParams = new URLSearchParams("");

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: (href: string) => {
      replaceMock(href);
      const url = new URL(href, "http://localhost");
      currentSearchParams = url.searchParams;
    },
    push: vi.fn(),
  }),
  usePathname: () => "/directory/personnel/lk",
  useSearchParams: () => currentSearchParams,
}));

vi.mock("@/components/TaskOrgFiltersBar", () => ({
  default: () => <div data-testid="task-org-filters-bar" />,
}));

vi.mock("./PersonnelApplicationRegisterDrawer", () => ({
  default: ({
    open,
    onRegistered,
  }: {
    open: boolean;
    onRegistered: (result: {
      application_id: number;
      person_id: number;
      action: "created";
      card_href: string;
    }) => void;
  }) =>
    open ? (
      <div data-testid="mock-register-drawer">
        <button
          type="button"
          data-testid="mock-register-success"
          onClick={() =>
            onRegistered({
              application_id: 42,
              person_id: 5,
              action: "created",
              card_href: "/directory/personnel/persons/5/card",
            })
          }
        >
          register
        </button>
      </div>
    ) : null,
}));

vi.mock("./PersonnelApplicationDetailDrawer", () => ({
  default: ({
    open,
    applicationId,
    journalReturnHref,
    onClose,
  }: {
    open: boolean;
    applicationId: number | null;
    journalReturnHref: string;
    onClose: () => void;
  }) =>
    open ? (
      <div data-testid="mock-detail-drawer" data-return-href={journalReturnHref}>
        detail #{applicationId}
        <button type="button" onClick={onClose} data-testid="mock-detail-close">
          close
        </button>
      </div>
    ) : null,
}));

const listPersonnelLkRegistryMock = vi.fn();
const bulkDeleteEmployeesMock = vi.fn();

vi.mock("../_lib/personnelLkApi.client", () => ({
  listPersonnelLkRegistry: (...args: unknown[]) => listPersonnelLkRegistryMock(...args),
  mapPersonnelLkApiError: (e: unknown, fallback: string) =>
    e instanceof Error ? e.message : fallback,
}));

vi.mock("../../employees/_lib/api.client", () => ({
  bulkDeleteEmployees: (...args: unknown[]) => bulkDeleteEmployeesMock(...args),
}));

const employeeRow: PersonnelLkRegistryItem = {
  person_id: 7,
  record_kind: "employee",
  id: 100,
  employee_id: 100,
  active_application_id: null,
  fio: "Иванов Иван",
  iin: "900101300111",
  rate: 1,
  status: "active",
  application_status: null,
};

const employeeRowTwo: PersonnelLkRegistryItem = {
  person_id: 8,
  record_kind: "employee",
  id: 101,
  employee_id: 101,
  active_application_id: null,
  fio: "Сидоров Сидор",
  iin: "900101300222",
  rate: 1,
  status: "active",
  application_status: null,
};

const applicantRow: PersonnelLkRegistryItem = {
  person_id: 5,
  record_kind: "applicant",
  id: null,
  employee_id: null,
  active_application_id: 10,
  fio: "Петров Пётр",
  iin: "900101300123",
  rate: 0.75,
  status: "applicant",
  application_status: "registered",
};

beforeEach(() => {
  currentSearchParams = new URLSearchParams("");
  replaceMock.mockClear();
  listPersonnelLkRegistryMock.mockReset();
  bulkDeleteEmployeesMock.mockReset();
  listPersonnelLkRegistryMock.mockResolvedValue({
    items: [employeeRow, applicantRow],
    total: 2,
    limit: 50,
    offset: 0,
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderWithMe(me: MeInfo | null) {
  return render(
    <CurrentUserProvider value={me}>
      <PersonnelLkPageClient />
    </CurrentUserProvider>,
  );
}

describe("PersonnelLkPageClient", () => {
  it("renders both record kinds and calls registry API with default filters", async () => {
    render(<PersonnelLkPageClient />);

    expect(await screen.findByTestId("personnel-lk-page")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Личные карточки" })).toBeInTheDocument();
    expect(screen.getByTestId("personnel-lk-row-employee-7")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-lk-row-applicant-5")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-lk-row-employee-7")).toHaveTextContent("Сотрудник");
    expect(screen.getByTestId("personnel-lk-row-applicant-5")).toHaveTextContent("Претендент");

    await waitFor(() => {
      expect(listPersonnelLkRegistryMock).toHaveBeenCalledWith({
        q: undefined,
        record_kind: undefined,
        status: "active",
        application_status: undefined,
        limit: 50,
        offset: 0,
        org_group_id: undefined,
        org_unit_id: undefined,
        position_id: undefined,
      });
    });
  });

  it("passes type and status filters to API", async () => {
    currentSearchParams = new URLSearchParams(
      "record_kind=applicant&status=all&application_status=registered&q=petrov",
    );
    render(<PersonnelLkPageClient />);

    await waitFor(() => {
      expect(listPersonnelLkRegistryMock).toHaveBeenCalledWith(
        expect.objectContaining({
          q: "petrov",
          record_kind: "applicant",
          status: "all",
          application_status: "registered",
        }),
      );
    });
  });

  it("opens employee card link with return_to", async () => {
    render(<PersonnelLkPageClient />);
    const link = await screen.findByTestId("personnel-lk-open-card-7");
    expect(link).toHaveAttribute("href", "/directory/personnel/persons/7/card?return_to=%2Fdirectory%2Fpersonnel%2Flk");
  });

  it("opens applicant drawer and preserves return href", async () => {
    const view = render(<PersonnelLkPageClient />);
    fireEvent.click(await screen.findByTestId("personnel-lk-open-application-10"));

    expect(replaceMock).toHaveBeenCalledWith("/directory/personnel/lk?application_id=10");
    const lastHref = String(replaceMock.mock.calls.at(-1)?.[0]);
    currentSearchParams = new URL(lastHref, "http://localhost").searchParams;
    view.rerender(<PersonnelLkPageClient />);

    expect(screen.getByTestId("mock-detail-drawer")).toHaveAttribute(
      "data-return-href",
      "/directory/personnel/lk?application_id=10",
    );
  });

  it("auto-opens drawer for application_id deep link", async () => {
    currentSearchParams = new URLSearchParams("application_id=10");
    render(<PersonnelLkPageClient />);

    expect(await screen.findByTestId("mock-detail-drawer")).toHaveTextContent("detail #10");
  });

  it("paginates using server total and clears selection on page change", async () => {
    listPersonnelLkRegistryMock.mockResolvedValueOnce({
      items: [employeeRow, employeeRowTwo],
      total: 120,
      limit: 50,
      offset: 0,
    });
    renderWithMe({
      user_id: 1,
      role_id: 2,
      is_system_admin: true,
      can_hard_delete_employee: true,
    });

    expect(await screen.findByTestId("personnel-lk-total")).toHaveTextContent("Всего: 120");
    fireEvent.click(screen.getByTestId("personnel-lk-select-employee-100"));
    fireEvent.click(screen.getByTestId("personnel-lk-select-employee-101"));
    expect(screen.getByTestId("personnel-lk-selected-count")).toHaveTextContent("Выбрано: 2");

    fireEvent.click(screen.getByTestId("personnel-lk-page-next"));
    expect(replaceMock).toHaveBeenCalledWith("/directory/personnel/lk?offset=50");
  });

  it("opens register drawer when register=1 is present", async () => {
    currentSearchParams = new URLSearchParams("register=1");
    render(<PersonnelLkPageClient />);
    expect(await screen.findByTestId("mock-register-drawer")).toBeInTheDocument();
  });

  it("shows bulk selection only for system admin and never for applicants", async () => {
    renderWithMe({
      user_id: 1,
      role_id: 2,
      is_system_admin: true,
      can_hard_delete_employee: true,
    });

    expect(await screen.findByTestId("personnel-lk-select-employee-100")).toBeInTheDocument();
    expect(screen.queryByTestId("personnel-lk-bulk-panel")).not.toBeInTheDocument();
    expect(screen.queryByTestId("personnel-lk-select-employee-10")).not.toBeInTheDocument();
    expect(screen.queryByTestId("personnel-lk-delete-employee-100")).not.toBeInTheDocument();
  });

  describe("bulk delete panel visibility", () => {
    const adminMe: MeInfo = {
      user_id: 1,
      role_id: 2,
      is_system_admin: true,
      can_hard_delete_employee: true,
    };

    it("does not show the panel when nothing is selected", async () => {
      renderWithMe(adminMe);

      expect(await screen.findByTestId("personnel-lk-select-employee-100")).toBeInTheDocument();
      expect(screen.queryByTestId("personnel-lk-bulk-panel")).not.toBeInTheDocument();
    });

    it("shows the panel after selecting employees", async () => {
      renderWithMe(adminMe);

      fireEvent.click(await screen.findByTestId("personnel-lk-select-employee-100"));

      expect(screen.getByTestId("personnel-lk-bulk-panel")).toBeInTheDocument();
      expect(screen.getByTestId("personnel-lk-selected-count")).toHaveTextContent("Выбрано: 1");
    });

    it("hides the panel after all selected employees are deleted successfully", async () => {
      vi.stubGlobal("confirm", vi.fn(() => true));
      bulkDeleteEmployeesMock.mockResolvedValue({
        requested: 1,
        deleted: [{ employee_id: 100, full_name: "Иванов Иван", person_deleted: true }],
        failed: [],
      });
      renderWithMe(adminMe);

      fireEvent.click(await screen.findByTestId("personnel-lk-select-employee-100"));
      expect(screen.getByTestId("personnel-lk-bulk-panel")).toBeInTheDocument();
      fireEvent.click(screen.getByTestId("personnel-lk-bulk-delete-btn"));

      await waitFor(() => expect(bulkDeleteEmployeesMock).toHaveBeenCalledWith([100]));
      await waitFor(() => expect(screen.queryByTestId("personnel-lk-bulk-panel")).not.toBeInTheDocument());
    });

    it("keeps the panel visible with remaining failed selection count on partial success", async () => {
      listPersonnelLkRegistryMock.mockResolvedValueOnce({
        items: [employeeRow, employeeRowTwo, applicantRow],
        total: 3,
        limit: 50,
        offset: 0,
      });
      vi.stubGlobal("confirm", vi.fn(() => true));
      bulkDeleteEmployeesMock.mockResolvedValue({
        requested: 2,
        deleted: [{ employee_id: 100, full_name: "Иванов Иван", person_deleted: true }],
        failed: [
          {
            employee_id: 101,
            error_code: "CONFLICT",
            message: "Не удалось удалить сотрудника: связанные данные заблокировали операцию.",
          },
        ],
      });
      renderWithMe(adminMe);

      fireEvent.click(await screen.findByTestId("personnel-lk-select-employee-100"));
      fireEvent.click(screen.getByTestId("personnel-lk-select-employee-101"));
      fireEvent.click(screen.getByTestId("personnel-lk-bulk-delete-btn"));

      await waitFor(() => expect(bulkDeleteEmployeesMock).toHaveBeenCalledWith([100, 101]));
      expect(screen.getByTestId("personnel-lk-bulk-panel")).toBeInTheDocument();
      expect(screen.getByTestId("personnel-lk-selected-count")).toHaveTextContent("Выбрано: 1");
      expect(screen.getByTestId("personnel-lk-select-employee-101")).toBeChecked();
    });
  });

  it("does not show bulk delete controls for a non-system-admin profile", async () => {
    renderWithMe({
      user_id: 34,
      role_id: 68,
      is_system_admin: false,
      has_sysadmin_api: true,
      can_hard_delete_employee: false,
    });

    await screen.findByTestId("personnel-lk-row-employee-7");
    expect(screen.queryByTestId("personnel-lk-bulk-panel")).not.toBeInTheDocument();
    expect(screen.queryByTestId("personnel-lk-select-employee-100")).not.toBeInTheDocument();
  });

  it("select-all toggles only employee rows on the current page", async () => {
    listPersonnelLkRegistryMock.mockResolvedValueOnce({
      items: [employeeRow, employeeRowTwo, applicantRow],
      total: 3,
      limit: 50,
      offset: 0,
    });
    renderWithMe({
      user_id: 1,
      role_id: 2,
      is_system_admin: true,
      can_hard_delete_employee: true,
    });

    fireEvent.click(await screen.findByTestId("personnel-lk-select-all"));
    expect(screen.getByTestId("personnel-lk-bulk-panel")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-lk-selected-count")).toHaveTextContent("Выбрано: 2");
    expect(screen.getByTestId("personnel-lk-select-employee-100")).toBeChecked();
    expect(screen.getByTestId("personnel-lk-select-employee-101")).toBeChecked();

    fireEvent.click(screen.getByTestId("personnel-lk-select-all"));
    expect(screen.queryByTestId("personnel-lk-bulk-panel")).not.toBeInTheDocument();
  });

  it("cancels bulk delete confirmation without calling API", async () => {
    const confirmMock = vi.fn(() => false);
    vi.stubGlobal("confirm", confirmMock);
    renderWithMe({
      user_id: 1,
      role_id: 2,
      is_system_admin: true,
      can_hard_delete_employee: true,
    });

    fireEvent.click(await screen.findByTestId("personnel-lk-select-employee-100"));
    fireEvent.click(screen.getByTestId("personnel-lk-bulk-delete-btn"));

    expect(confirmMock).toHaveBeenCalledWith(expect.stringContaining("Иванов Иван"));
    expect(confirmMock).toHaveBeenCalledWith(
      expect.stringContaining("без возможности восстановления"),
    );
    expect(bulkDeleteEmployeesMock).not.toHaveBeenCalled();
  });

  it("confirms bulk delete and removes successful employee rows", async () => {
    const confirmMock = vi.fn(() => true);
    vi.stubGlobal("confirm", confirmMock);
    bulkDeleteEmployeesMock.mockResolvedValue({
      requested: 1,
      deleted: [{ employee_id: 100, full_name: "Иванов Иван", person_deleted: true }],
      failed: [],
    });
    renderWithMe({
      user_id: 1,
      role_id: 2,
      is_system_admin: true,
      can_hard_delete_employee: true,
    });

    fireEvent.click(await screen.findByTestId("personnel-lk-select-employee-100"));
    fireEvent.click(screen.getByTestId("personnel-lk-bulk-delete-btn"));

    await waitFor(() => expect(bulkDeleteEmployeesMock).toHaveBeenCalledWith([100]));
    await waitFor(() =>
      expect(screen.queryByTestId("personnel-lk-row-employee-7")).not.toBeInTheDocument(),
    );
    expect(screen.getByTestId("personnel-lk-row-applicant-5")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-lk-total")).toHaveTextContent("Всего: 1");
    expect(screen.getByTestId("personnel-lk-bulk-summary-text")).toHaveTextContent("Удалён 1 сотрудник.");
    expect(screen.queryByTestId("personnel-lk-bulk-panel")).not.toBeInTheDocument();
  });

  it("keeps failed rows selected and shows partial success summary", async () => {
    listPersonnelLkRegistryMock.mockResolvedValueOnce({
      items: [employeeRow, employeeRowTwo, applicantRow],
      total: 3,
      limit: 50,
      offset: 0,
    });
    vi.stubGlobal("confirm", vi.fn(() => true));
    bulkDeleteEmployeesMock.mockResolvedValue({
      requested: 2,
      deleted: [{ employee_id: 100, full_name: "Иванов Иван", person_deleted: true }],
      failed: [
        {
          employee_id: 101,
          error_code: "CONFLICT",
          message: "Не удалось удалить сотрудника: связанные данные заблокировали операцию.",
        },
      ],
    });
    renderWithMe({
      user_id: 1,
      role_id: 2,
      is_system_admin: true,
      can_hard_delete_employee: true,
    });

    fireEvent.click(await screen.findByTestId("personnel-lk-select-employee-100"));
    fireEvent.click(screen.getByTestId("personnel-lk-select-employee-101"));
    fireEvent.click(screen.getByTestId("personnel-lk-bulk-delete-btn"));

    await waitFor(() => expect(bulkDeleteEmployeesMock).toHaveBeenCalledWith([100, 101]));
    expect(screen.queryByTestId("personnel-lk-row-employee-7")).not.toBeInTheDocument();
    expect(screen.getByTestId("personnel-lk-row-employee-8")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-lk-selected-count")).toHaveTextContent("Выбрано: 1");
    expect(screen.getByTestId("personnel-lk-select-employee-101")).toBeChecked();
    expect(screen.getByTestId("personnel-lk-bulk-summary-text")).toHaveTextContent(
      "Удалено: 1. Не удалено: 1.",
    );
    expect(screen.getByText(/Сидоров Сидор:/)).toBeInTheDocument();
  });

  it("shows API error when bulk delete request fails entirely", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    bulkDeleteEmployeesMock.mockRejectedValue(new Error("HTTP 403: forbidden"));
    renderWithMe({
      user_id: 1,
      role_id: 2,
      is_system_admin: true,
      can_hard_delete_employee: true,
    });

    fireEvent.click(await screen.findByTestId("personnel-lk-select-employee-100"));
    fireEvent.click(screen.getByTestId("personnel-lk-bulk-delete-btn"));

    expect(await screen.findByText("HTTP 403: forbidden")).toBeInTheDocument();
    expect(screen.getByTestId("personnel-lk-row-employee-7")).toBeInTheDocument();
  });
});
