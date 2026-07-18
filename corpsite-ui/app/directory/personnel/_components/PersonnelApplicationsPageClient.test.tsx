import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PersonnelApplicationsPageClient from "./PersonnelApplicationsPageClient";
import type { PersonnelApplicationListItem } from "../_lib/personnelApplicationsApi.client";

const replaceMock = vi.fn();
const pushMock = vi.fn();
let currentSearchParams = new URLSearchParams("");

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: (href: string) => {
      replaceMock(href);
      const url = new URL(href, "http://localhost");
      currentSearchParams = url.searchParams;
    },
    push: pushMock,
  }),
  usePathname: () => "/directory/personnel/applicants",
  useSearchParams: () => currentSearchParams,
}));

vi.mock("./PersonnelSubNav", () => ({
  default: () => <nav data-testid="personnel-sub-nav">subnav</nav>,
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

const listPersonnelApplicationsMock = vi.fn();

vi.mock("../_lib/personnelApplicationsApi.client", async () => {
  const actual = await vi.importActual<typeof import("../_lib/personnelApplicationsApi.client")>(
    "../_lib/personnelApplicationsApi.client",
  );
  return {
    ...actual,
    listPersonnelApplications: (...args: unknown[]) => listPersonnelApplicationsMock(...args),
  };
});

const sampleItem: PersonnelApplicationListItem = {
  application_id: 10,
  person_id: 5,
  full_name: "Петров Пётр Петрович",
  iin: "900101300123",
  status: "registered",
  application_received_at: "2026-07-01",
  intended_org_group_id: 1,
  intended_org_unit_id: 2,
  intended_position_id: 3,
  intended_org_group_name: "Группа",
  intended_org_unit_name: "Терапия",
  intended_position_name: "Медсестра",
  registered_at: "2026-07-02T10:00:00Z",
  registered_by_user_id: 7,
  registered_by_name: "HR User",
  director_resolution_status: null,
  personnel_order_id: null,
  is_active: true,
  intake_link_status: null,
  intake_draft_status: null,
  intake_opened_at: null,
  intake_submitted_at: null,
  employee_id: null,
  employee_full_name: null,
  completed_at: null,
  closed_at: null,
  is_read_only: false,
};

function renderJournal(query = "") {
  currentSearchParams = new URLSearchParams(query);
  return render(<PersonnelApplicationsPageClient />);
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  currentSearchParams = new URLSearchParams("");
});

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

describe("PersonnelApplicationsPageClient journal UX", () => {
  it("renders page and loads journal", async () => {
    listPersonnelApplicationsMock.mockResolvedValue({ items: [sampleItem], total: 1, limit: 50, offset: 0 });
    renderJournal();

    await waitFor(() => {
      expect(screen.getByTestId("personnel-applications-table")).toBeInTheDocument();
    });
    expect(listPersonnelApplicationsMock).toHaveBeenCalledTimes(1);
  });

  it("restores deep-linked drawer and filters from URL (F5 simulation)", async () => {
    listPersonnelApplicationsMock.mockResolvedValue({ items: [sampleItem], total: 1, limit: 50, offset: 0 });
    renderJournal("q=petrov&application_id=10&offset=0");

    await waitFor(() => {
      expect(screen.getByTestId("mock-detail-drawer")).toHaveTextContent("detail #10");
    });
    expect(screen.getByTestId("personnel-applications-search")).toHaveValue("petrov");
    expect(listPersonnelApplicationsMock).toHaveBeenCalledWith(
      expect.objectContaining({ q: "petrov", offset: 0 }),
    );
  });

  it("writes application_id to URL when row is clicked", async () => {
    listPersonnelApplicationsMock.mockResolvedValue({ items: [sampleItem], total: 1, limit: 50, offset: 0 });
    const view = renderJournal("q=petrov");

    await waitFor(() => {
      expect(screen.getByTestId("personnel-application-row-10")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("personnel-application-row-10"));

    expect(replaceMock).toHaveBeenCalledWith(
      "/directory/personnel/applicants?q=petrov&application_id=10",
    );

    const lastHref = String(replaceMock.mock.calls.at(-1)?.[0]);
    currentSearchParams = new URL(lastHref, "http://localhost").searchParams;
    view.rerender(<PersonnelApplicationsPageClient />);

    expect(screen.getByTestId("mock-detail-drawer")).toBeInTheDocument();
  });

  it("closes drawer when URL loses application_id (browser Back simulation)", async () => {
    listPersonnelApplicationsMock.mockResolvedValue({ items: [sampleItem], total: 1, limit: 50, offset: 0 });
    const view = renderJournal("q=petrov&application_id=10");

    await waitFor(() => {
      expect(screen.getByTestId("mock-detail-drawer")).toBeInTheDocument();
    });

    currentSearchParams = new URLSearchParams("q=petrov");
    view.rerender(<PersonnelApplicationsPageClient />);

    await waitFor(() => {
      expect(screen.queryByTestId("mock-detail-drawer")).not.toBeInTheDocument();
    });
  });

  it("persists search to URL on Enter", async () => {
    listPersonnelApplicationsMock.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    renderJournal();

    await waitFor(() => {
      expect(screen.getByTestId("personnel-applications-search")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("personnel-applications-search"), {
      target: { value: "Иванов" },
    });
    fireEvent.keyDown(screen.getByTestId("personnel-applications-search"), { key: "Enter" });

    expect(replaceMock).toHaveBeenCalledWith("/directory/personnel/applicants?q=%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2");
  });

  it("after registration refreshes journal, highlights row and opens detail while keeping filters", async () => {
    listPersonnelApplicationsMock
      .mockResolvedValueOnce({ items: [], total: 0, limit: 50, offset: 0 })
      .mockResolvedValueOnce({
        items: [{ ...sampleItem, application_id: 42, full_name: "Новый Претендент" }],
        total: 1,
        limit: 50,
        offset: 0,
      });

    renderJournal("q=petrov&org_unit_id=2");

    await waitFor(() => {
      expect(screen.getByTestId("personnel-applications-empty")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("personnel-applications-register-button"));
    fireEvent.click(screen.getByTestId("mock-register-success"));

    await waitFor(() => {
      expect(screen.getByTestId("mock-detail-drawer")).toBeInTheDocument();
    });

    expect(screen.queryByTestId("personnel-applications-toast")).not.toBeInTheDocument();

    expect(pushMock).not.toHaveBeenCalled();
    expect(replaceMock).toHaveBeenCalledWith(
      expect.stringContaining("application_id=42"),
    );
    expect(replaceMock).toHaveBeenCalledWith(expect.stringContaining("q=petrov"));
    expect(replaceMock).toHaveBeenCalledWith(expect.stringContaining("org_unit_id=2"));

    await waitFor(() => {
      expect(screen.getByTestId("personnel-application-row-42")).toHaveAttribute("data-highlighted", "true");
    });
    expect(listPersonnelApplicationsMock.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it("passes journal return href to detail drawer for card navigation", async () => {
    listPersonnelApplicationsMock.mockResolvedValue({ items: [sampleItem], total: 1, limit: 50, offset: 0 });
    renderJournal("q=petrov&application_id=10");

    await waitFor(() => {
      expect(screen.getByTestId("mock-detail-drawer")).toBeInTheDocument();
    });

    expect(screen.getByTestId("mock-detail-drawer")).toHaveAttribute(
      "data-return-href",
      "/directory/personnel/applicants?q=petrov&application_id=10",
    );
  });

  it("does not refetch list when only application_id changes", async () => {
    listPersonnelApplicationsMock.mockResolvedValue({ items: [sampleItem], total: 1, limit: 50, offset: 0 });
    const view = renderJournal("q=petrov");

    await waitFor(() => {
      expect(listPersonnelApplicationsMock).toHaveBeenCalledTimes(1);
    });

    currentSearchParams = new URLSearchParams("q=petrov&application_id=10");
    view.rerender(<PersonnelApplicationsPageClient />);

    await waitFor(() => {
      expect(screen.getByTestId("mock-detail-drawer")).toBeInTheDocument();
    });
    expect(listPersonnelApplicationsMock).toHaveBeenCalledTimes(1);
  });

  it("switches to archive view and requests archive list", async () => {
    listPersonnelApplicationsMock.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    const view = renderJournal();

    await waitFor(() => {
      expect(screen.getByTestId("personnel-applications-view-archive")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("personnel-applications-view-archive"));

    expect(replaceMock).toHaveBeenCalledWith(
      "/directory/personnel/applicants?view=archive&sort=closed_at_desc",
    );

    const lastHref = String(replaceMock.mock.calls.at(-1)?.[0]);
    currentSearchParams = new URL(lastHref, "http://localhost").searchParams;
    view.rerender(<PersonnelApplicationsPageClient />);

    await waitFor(() => {
      expect(listPersonnelApplicationsMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ view: "archive", sort: "closed_at_desc" }),
      );
    });
  });
});
