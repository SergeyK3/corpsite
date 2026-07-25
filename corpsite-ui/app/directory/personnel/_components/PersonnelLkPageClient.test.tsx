import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelLkPageClient from "./PersonnelLkPageClient";
import type { PersonnelLkRegistryItem } from "../_lib/personnelLkApi.client";

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

vi.mock("../_lib/personnelLkApi.client", () => ({
  listPersonnelLkRegistry: (...args: unknown[]) => listPersonnelLkRegistryMock(...args),
  mapPersonnelLkApiError: (e: unknown, fallback: string) =>
    e instanceof Error ? e.message : fallback,
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
  listPersonnelLkRegistryMock.mockResolvedValue({
    items: [employeeRow, applicantRow],
    total: 2,
    limit: 50,
    offset: 0,
  });
});

afterEach(() => {
  cleanup();
});

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

  it("paginates using server total", async () => {
    listPersonnelLkRegistryMock.mockResolvedValueOnce({
      items: [employeeRow],
      total: 120,
      limit: 50,
      offset: 0,
    });
    render(<PersonnelLkPageClient />);

    expect(await screen.findByTestId("personnel-lk-total")).toHaveTextContent("Всего: 120");
    fireEvent.click(screen.getByTestId("personnel-lk-page-next"));
    expect(replaceMock).toHaveBeenCalledWith("/directory/personnel/lk?offset=50");
  });

  it("opens register drawer when register=1 is present", async () => {
    currentSearchParams = new URLSearchParams("register=1");
    render(<PersonnelLkPageClient />);
    expect(await screen.findByTestId("mock-register-drawer")).toBeInTheDocument();
  });
});
